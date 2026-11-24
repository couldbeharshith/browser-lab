# Cloud Browser Automation Proof of Concept

**Approved proof of concept**

## Project idea

Upload a batch of Python Playwright scripts. Each script runs in its own Kubernetes Job. The dashboard shows batch progress and lets the operator inspect each check’s result, logs, screenshot, and optional video. The operator uses a regular browser to access the dashboard.

The project demonstrates asynchronous execution, Kubernetes scheduling, and concurrent browser runs in a short classroom demo.

## Demo scope

- **One dashboard.** Submit a named batch, switch between recent batches, and inspect each check. The worker timeline shows when executions overlap.
- **One script interface.** Upload up to eight `.py` files of 64 KiB each. Each starts with a module docstring describing the steps and defines a synchronous `run(page)` function. The worker supplies a Chromium page. The script can use Playwright assertions and log steps with `print()`.
- **One Kubernetes node on AWS EC2.** FastAPI creates one Kubernetes Job per run. Each Job launches a short-lived browser worker, and the dashboard shows `Pending`, `Running`, `Succeeded`, or `Failed` from Kubernetes status. A Job deadline stops runs that hang. [Kubernetes Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/)
- **One shared volume.** The API stores batch metadata and uploaded scripts. Workers save artifacts under their run IDs. [Kubernetes persistent volumes](https://kubernetes.io/docs/concepts/storage/persistent-volumes/)
- **Two Docker images.** One packages FastAPI, the dashboard, and the sample shop. The other packages Playwright, Chromium, and the script runner.

The demo uses team-authored scripts and a private dashboard reached through an SSH tunnel to the EC2 instance. The shop examples use the worker’s `DEMO_BASE_URL` environment variable to reach the bundled shop.

## Demo acceptance criteria

1. Submit a batch containing the login-and-search and add-to-cart scripts. Confirm two separate jobs pass and that each has its own screenshot and logs.
2. Inspect the worker timeline to confirm their execution intervals overlap.
3. Submit the wrong-total script. Show the failed assertion, shop screenshot, and traceback. Enable recording on a batch to show the video playback.

## Run the demo on EC2

Use one Ubuntu EC2 instance with at least 2 vCPUs and 4 GiB of RAM for the cluster and two browser workers. Allow SSH from the operator’s IP in the instance security group. The commands below use an x86-64 instance and the Ubuntu SSH user. [K3s requirements](https://docs.k3s.io/installation/requirements) · [EC2 SSH access](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/connect-to-linux-instance.html)

From the project root, build both images with Docker and send them to the instance. Replace `EC2_HOST` with the host name or IP. Use your configured SSH key for `scp` and `ssh`.

```sh
docker compose build
docker save --output browser-demo-images.tar browser-demo-api:1 browser-demo-worker:1
scp browser-demo-images.tar k8s/browser-demo.yaml ubuntu@EC2_HOST:
ssh ubuntu@EC2_HOST
```

On the EC2 host, install K3s if needed, then import the images and apply the manifest. [K3s installation](https://docs.k3s.io/quick-start) · [K3s image import](https://docs.k3s.io/add-ons/import-images)

```sh
curl -sfL https://get.k3s.io | sh -s - server --disable traefik --disable servicelb
sudo k3s ctr images import browser-demo-images.tar
sudo k3s kubectl apply -f browser-demo.yaml
sudo k3s kubectl -n browser-demo rollout status deployment/browser-demo-api
```

From your computer, open the SSH tunnel and leave it running during the demo.

```sh
ssh -L 8000:127.0.0.1:8000 ubuntu@EC2_HOST "sudo k3s kubectl -n browser-demo port-forward service/browser-demo-api 8000:8000"
```

Open `http://127.0.0.1:8000` and choose the `.py` files from one folder under `temp/browser-lab-demos`. Drop the files onto the dashboard or choose them under **New batch**. Enable **Record a video for each check** to capture the replay. To load a bundled set directly, expand **Load example scripts** in the upload dialog and choose a batch.

- **Catalog discovery** checks sign-in and search, empty-search recovery, and how search combines with product categories.
- **Cart journeys** checks quantities and totals, completes a demo checkout, and verifies that the bag survives a reload.
- **Regression replay** checks item removal and sign-in validation alongside a deliberate cart-total failure.

Sample recordings use visible typing, click indicators, and numbered step captions with pauses. On a 4 GiB EC2 host, start with one batch at a time for the demo.

To watch the workers from a second EC2 shell, run `sudo k3s kubectl -n browser-demo get pods -w`.

Based on the [original project presentation](Cloud_Browser_Automation_Platform.pdf).
