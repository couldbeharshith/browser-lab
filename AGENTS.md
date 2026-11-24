# AGENTS.md

This file provides guidance to all AI Agents when working with code in this repository.

## Project

This is a private runner for batches of team-authored Python Playwright checks on single-node Kubernetes on AWS EC2. The demo uses sample scripts for a shop login and search, a cart check, and an intentional assertion failure.

- `api/` serves the batch dashboard, run API, shop fixture, and sample scripts with FastAPI and Uvicorn.
- `worker/` executes one script in headless Chromium and saves its evidence.
- `k8s/` defines the API deployment, internal service, RBAC, and shared artifact volume.
- `idea/PROJECT_PROPOSAL.md` records the approved scope and EC2 commands.

## Commands

```text
# Deploy the published Docker Hub images to Ubuntu EC2 and open the dashboard tunnel.
.\Deploy-BrowserLab.ps1 -Ec2Host 'YOUR_EC2_PUBLIC_IP' -KeyPath 'C:\keys\your-key.pem'
# Build both images before publishing a new version. See README.md for the tag and push commands.
docker compose build

# In a Bash shell, install headless Chromium for a standalone worker run.
uv run --locked --only-group worker playwright install --only-shell chromium
# Run the original standalone heading check and save outputs in the ignored scratch directory.
ARTIFACT_DIR=./agent_temp/artifacts uv run --locked --only-group worker python worker/run.py demo-pass pass
# Package the two built images for transfer to the EC2 host.
docker save --output browser-demo-images.tar browser-demo-api:1 browser-demo-worker:1
# On the K3s host, import the uploaded images.
sudo k3s ctr images import browser-demo-images.tar
# Apply the uploaded manifest from the same directory.
sudo k3s kubectl apply -f browser-demo.yaml
# Run on the host and access port 8000 through an SSH tunnel.
sudo k3s kubectl -n browser-demo port-forward service/browser-demo-api 8000:8000
```

## Runtime Dependencies

- The API starts using in-cluster service account credentials. It needs namespaced permissions to create and list Jobs and list Pods.
- K3s needs both images and the `local-path` StorageClass. The deploy script pulls published images from Docker Hub. Applying the base manifest directly requires importing the local tags. A missing StorageClass leaves the `artifacts` claim unbound.
- The worker image supplies Chromium. The bundled examples use `DEMO_BASE_URL`, set to the internal API service’s shop page. An EC2 SSH login provides dashboard access. The application requires no API keys, database, or broker.

## Architecture

1. `api/dashboard.html` sends the selected `.py` files to `POST /api/batches`. `create_batch` saves batch metadata and one `script.py` per run on the shared volume, then creates one Kubernetes Job per run.
2. `run_uploaded_check` in `worker/run.py` calls each script’s synchronous `run(page)` and writes its result, logs, screenshot, and optional video under `/artifacts/<run-id>/`.
3. The dashboard polls `GET /api/batches`. `list_batches` joins batch metadata with Job and Pod status. The worker timeline uses container start and finish timestamps.

### Non-obvious details

- `submit_job` sets a 60-second deadline and zero backoff retries. Each worker requests 100m CPU and 256 MiB RAM, with limits of 1 CPU and 768 MiB. `BatchRequest` accepts up to 10 distinct `.py` files of 64 KiB each. Keep the dashboard upload cap in sync. The API reads the required module docstrings with `ast` before it submits jobs. Uploaded code is for private, team-authored demos.
- `describe_run` uses Job terminal conditions and the Pod’s running phase. A created Job can be `Pending` before its worker pod starts.
- The base manifest uses `Never` for both images. `Deploy-BrowserLab.ps1` renders it with Docker Hub tags and `IfNotPresent`, including the worker settings `WORKER_IMAGE` and `WORKER_IMAGE_PULL_POLICY`.
- The API and workers mount the shared claim read-write. Batch metadata, screenshots, and final result files are renamed into place after writing. `ARTIFACT_DIR` defaults to that mount and can be overridden for a standalone worker run.
- `DELETE /api/batches/{batch_id}` archives the metadata for a finished batch under `history-archive/deleted-batches/` on the shared volume. Per-run artifacts are retained.

## Misc

- Compose builds the images. Kubernetes runs the app. The repository has no test suite, linter, formatter, or seed step.

## General Working Rules (User Preferences)

- **Ignore `./temp/` completely.** Never read from it. It is the User's scratchpad.
- **Never `git commit` or `git push`.** The User reviews and commits by hand. `git pull` is fine.
- **Keep it simple.** Treat this as a hobby project unless told it is production. Don't overengineer.
- **No tests** unless the user asks. You may ask before a coding session starts.
- **Minimal comments.** Use descriptive names so the code explains itself.
- **Docs:** don't write a new `.md` per change. Ask first. If yes, update an existing `.md` or this file.
- **Python:** use `uv`, not pip, unless the project already uses pip. Keep `pyproject.toml` complete and current.
- **JS/TS:** use Bun for packages and scripts. Prefer TS over JS unless told otherwise.
- **New frontends:** latest Next.js unless told otherwise. **New backend APIs:** FastAPI.
- **Repo layout:** prefer a monorepo unless told otherwise.
- **CLI scaffolding (`bunx`/`npx`, etc.):** pass every option as flags so nothing prompts interactively. Ask the user about choices first if needed.
- **Docker:** use multi-stage builds and small base images. Multiple containers → Dockerfiles plus a `docker-compose.yml`.
- Keep `.gitignore` and `.env.example` in sync with changes.
- Use `./agent_temp` (gitignored) as a personal scratchpad for yourself or temp scripts/ data etc.
