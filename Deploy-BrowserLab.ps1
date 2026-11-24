[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidatePattern('^[a-zA-Z0-9][a-zA-Z0-9.-]*$')]
    [string]$Ec2Host,

    [Parameter(Mandatory)]
    [string]$KeyPath,

    [ValidatePattern('^[a-z0-9][a-z0-9_-]*$')]
    [string]$DockerHubUser = 'couldbeharshith',

    [ValidatePattern('\A[a-zA-Z0-9_][a-zA-Z0-9_.-]{0,127}\z')]
    [string]$ImageTag = 'v1',

    [ValidateRange(1024, 65535)]
    [int]$LocalPort = 8081,

    [switch]$TunnelOnly
)

$ErrorActionPreference = 'Stop'
$keyFile = (Resolve-Path -LiteralPath $KeyPath).ProviderPath
$remote = "ubuntu@$Ec2Host"
$sshOptions = @('-i', $keyFile, '-o', 'ConnectTimeout=10', '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=2')

function Invoke-Step {
    param([string]$Description, [string]$Command, [string[]]$Arguments)

    Write-Host "`n$Description"
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Command exited with code $LASTEXITCODE. See its output above."
    }
}

if (-not $TunnelOnly) {
    $apiImage = "docker.io/$DockerHubUser/browser-lab:api-$ImageTag"
    $workerImage = "docker.io/$DockerHubUser/browser-lab:worker-$ImageTag"
    $manifestName = "browser-lab-$([guid]::NewGuid()).yaml"
    $manifestPath = Join-Path ([System.IO.Path]::GetTempPath()) $manifestName
    $template = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'k8s/browser-demo.yaml') -Raw
    $manifest = $template.Replace('browser-demo-api:1', $apiImage).Replace('browser-demo-worker:1', $workerImage)
    $manifest = $manifest.Replace('imagePullPolicy: Never', 'imagePullPolicy: IfNotPresent').Replace('value: Never', 'value: IfNotPresent')
    try {
        [System.IO.File]::WriteAllText($manifestPath, $manifest)
        Invoke-Step "Connect to $remote and create the deployment directory (10-second connection timeout)." ssh ($sshOptions + @('-n', '-T', $remote, 'mkdir -p ~/browser-lab && echo SSH-ready'))
        Invoke-Step 'Copy the small Kubernetes manifest to EC2 over SSH.' scp ($sshOptions + @($manifestPath, "${remote}:browser-lab/"))

        $deploy = @(
            'cd ~/browser-lab',
            '(command -v k3s >/dev/null || (curl -fsSL https://get.k3s.io -o k3s-install.sh && sudo -n sh k3s-install.sh server --disable traefik --disable servicelb))',
            'sudo -n systemctl start k3s',
            'echo Waiting for the K3s node to register...',
            '(for attempt in $(seq 1 90); do if sudo -n k3s kubectl --request-timeout=2s get nodes -o name 2>/dev/null | grep -q ^node/; then exit 0; fi; sleep 2; done; echo K3s node did not register. >&2; exit 1)',
            'sudo -n k3s kubectl wait --for=condition=Ready node --all --timeout=180s',
            "sudo -n k3s ctr images pull $apiImage",
            "sudo -n k3s ctr images pull $workerImage",
            "sudo -n k3s kubectl apply -f $manifestName",
            "rm -f -- $manifestName",
            'sudo -n k3s kubectl -n browser-demo rollout status deployment/browser-demo-api --timeout=180s',
            'sudo -n k3s kubectl -n browser-demo get pods,svc,pvc'
        ) -join ' && '
        Invoke-Step 'Install K3s if needed, pull both images from Docker Hub, and wait for the API.' ssh ($sshOptions + @('-n', '-T', $remote, $deploy))
    }
    finally {
        if (Test-Path -LiteralPath $manifestPath) {
            Remove-Item -LiteralPath $manifestPath
        }
    }
}

Invoke-Step "Open http://127.0.0.1:$LocalPort/ after Forwarding appears. Ctrl+C closes the tunnel." ssh ($sshOptions + @(
    '-n', '-T', '-o', 'ExitOnForwardFailure=yes',
    '-L', "127.0.0.1:${LocalPort}:127.0.0.1:8000", $remote,
    'sudo -n k3s kubectl -n browser-demo port-forward --address 127.0.0.1 service/browser-demo-api 8000:8000'
))
