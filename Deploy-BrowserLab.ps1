[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidatePattern('^[a-zA-Z0-9][a-zA-Z0-9.-]*$')]
    [string]$Ec2Host,

    [Parameter(Mandatory)]
    [string]$KeyPath,

    [ValidateRange(1024, 65535)]
    [int]$LocalPort = 8081,

    [switch]$TunnelOnly
)

$ErrorActionPreference = 'Stop'
$keyFile = (Resolve-Path -LiteralPath $KeyPath).ProviderPath
$remote = "ubuntu@$Ec2Host"

function Invoke-Step {
    param([string]$Description, [string]$Command, [string[]]$Arguments)

    Write-Host "`n$Description"
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Command exited with code $LASTEXITCODE. See its output above."
    }
}

if (-not $TunnelOnly) {
    $archive = Join-Path ([System.IO.Path]::GetTempPath()) "browser-lab-$([guid]::NewGuid()).tar"
    Push-Location -LiteralPath $PSScriptRoot
    try {
        Invoke-Step 'Test SSH access and create the deployment directory on EC2.' ssh @('-i', $keyFile, $remote, 'mkdir -p ~/browser-lab')
        Invoke-Step 'Build the API and Playwright worker images with Docker Compose.' docker @('compose', 'build')
        Invoke-Step 'Pack both Docker images into a portable archive.' docker @('save', '--output', $archive, 'browser-demo-api:1', 'browser-demo-worker:1')
        Invoke-Step 'Copy the images and Kubernetes manifest to EC2 over SSH.' scp @('-i', $keyFile, $archive, '.\k8s\browser-demo.yaml', "${remote}:browser-lab/")

        $archiveName = Split-Path -Leaf $archive
        $deploy = @(
            'cd ~/browser-lab',
            '(command -v k3s >/dev/null || (curl -fsSL https://get.k3s.io -o k3s-install.sh && sudo -n sh k3s-install.sh server --disable traefik --disable servicelb))',
            'sudo -n systemctl start k3s',
            'sudo -n k3s kubectl wait --for=condition=Ready node --all --timeout=180s',
            "sudo -n k3s ctr images import $archiveName",
            "rm -f -- $archiveName",
            'existing=$(sudo -n k3s kubectl -n browser-demo get deployment/browser-demo-api --ignore-not-found -o name)',
            'sudo -n k3s kubectl apply -f browser-demo.yaml',
            'case $existing in deployment.apps/*) sudo -n k3s kubectl -n browser-demo rollout restart deployment/browser-demo-api ;; esac',
            'sudo -n k3s kubectl -n browser-demo rollout status deployment/browser-demo-api --timeout=180s',
            'sudo -n k3s kubectl -n browser-demo get pods,svc,pvc'
        ) -join ' && '
        Invoke-Step 'Install K3s if needed, import the images, apply the manifest, and wait for the API.' ssh @('-i', $keyFile, $remote, $deploy)
    }
    finally {
        if (Test-Path -LiteralPath $archive) {
            Remove-Item -LiteralPath $archive
        }
        Pop-Location
    }
}

Invoke-Step "Open http://127.0.0.1:$LocalPort/ after Forwarding appears. Ctrl+C closes the tunnel." ssh @(
    '-i', $keyFile, '-o', 'ExitOnForwardFailure=yes',
    '-L', "127.0.0.1:${LocalPort}:127.0.0.1:8000", $remote,
    'sudo -n k3s kubectl -n browser-demo port-forward --address 127.0.0.1 service/browser-demo-api 8000:8000'
)
