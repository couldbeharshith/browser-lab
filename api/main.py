import ast
import json
import logging
import os
import re
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
from pydantic import BaseModel, Field


NAMESPACE = os.environ.get("POD_NAMESPACE", "browser-demo")
WORKER_IMAGE = os.environ.get("WORKER_IMAGE", "browser-demo-worker:1")
WORKER_IMAGE_PULL_POLICY = os.environ.get("WORKER_IMAGE_PULL_POLICY", "Never")
ARTIFACTS = Path(os.environ.get("ARTIFACT_DIR", "/artifacts"))
WORKER_LABEL = "app.kubernetes.io/name=browser-demo-worker"
RUN_ID = re.compile(r"run-[0-9a-f]{32}")
BATCH_ID = re.compile(r"batch-[0-9a-f]{32}")
SCRIPT_NAME = re.compile(r"[\w .-]{1,75}\.py", re.ASCII)
SOURCE_FILES = Path(__file__).parent
EXAMPLE_BATCHES = {
    "catalog": ("Catalog discovery", ["01_login_and_search.py", "04_search_recovery.py", "07_category_filter.py"]),
    "cart": ("Cart journeys", ["02_add_to_cart.py", "05_checkout.py", "08_bag_persistence.py"]),
    "regression": ("Regression replay", ["06_remove_cart_item.py", "09_sign_in_validation.py", "03_wrong_cart_total.py"]),
}


class RunRequest(BaseModel):
    check: Literal["pass", "fail"]


class ScriptUpload(BaseModel):
    name: str = Field(max_length=78)
    source: str = Field(min_length=1, max_length=65_536)


class ScriptSet(BaseModel):
    scripts: list[ScriptUpload] = Field(min_length=1, max_length=10)


class BatchRequest(ScriptSet):
    name: str = Field(default="", max_length=80)
    record_video: bool = False


def script_description(source):
    return (ast.get_docstring(ast.parse(source.lstrip("\ufeff"))) or "").strip()


def inspect_script(script):
    description = ""
    if not SCRIPT_NAME.fullmatch(script.name) or len(script.source.encode("utf-8")) > 65_536:
        error = "Use a .py filename and a file up to 64 KiB."
    else:
        try:
            description = script_description(script.source)
        except SyntaxError as error_info:
            error = f"Python syntax error on line {error_info.lineno}: {error_info.msg}."
        except (ValueError, RecursionError):
            error = "This Python file could not be parsed."
        else:
            error = None if description else "Add a module docstring before the imports."
    return {"name": script.name, "description": description, "error": error}


@lru_cache(maxsize=32)
def bundled_description(name):
    if not SCRIPT_NAME.fullmatch(name):
        return "", ""
    try:
        source = (SOURCE_FILES / "examples" / name).read_text(encoding="utf-8")
    except FileNotFoundError:
        return "", ""
    module = ast.parse(source)
    description = ast.get_docstring(module) or ""
    return description, "".join(source.splitlines(keepends=True)[module.body[0].end_lineno:]).strip() if description else ""


@lru_cache(maxsize=512)
def historical_description(run_id, name):
    if not RUN_ID.fullmatch(run_id):
        return ""
    try:
        source = (ARTIFACTS / run_id / "script.py").read_text(encoding="utf-8")
        description = script_description(source)
    except (FileNotFoundError, UnicodeError, SyntaxError, ValueError, RecursionError):
        return ""
    if description:
        return description
    description, original = bundled_description(name)
    return description if description and source.strip() == original else ""


def write_json(path, payload):
    pending = path.with_suffix(".tmp")
    pending.write_text(json.dumps(payload), encoding="utf-8")
    pending.replace(path)


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.load_incluster_config()
    with client.ApiClient() as kubernetes:
        app.state.jobs = client.BatchV1Api(kubernetes)
        app.state.pods = client.CoreV1Api(kubernetes)
        yield


app = FastAPI(title="Browser Automation Demo", lifespan=lifespan)


@app.exception_handler(ApiException)
async def kubernetes_error(_request: Request, error: ApiException):
    logging.getLogger(__name__).warning("Kubernetes request failed (%s): %s", error.status, error.reason)
    return JSONResponse(status_code=503, content={"detail": "Kubernetes could not complete the request."})


@app.get("/", response_class=HTMLResponse)
def landing():
    return FileResponse(SOURCE_FILES / "landing.html", media_type="text/html")


@app.get("/landing/dashboard.png", include_in_schema=False)
def landing_preview():
    return FileResponse(SOURCE_FILES.parent / "docs" / "images" / "dashboard.png", media_type="image/png")


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return FileResponse(Path(__file__).with_name("dashboard.html"), media_type="text/html")


@app.get("/assets/brand.css", include_in_schema=False)
def brand_styles():
    return FileResponse(SOURCE_FILES / "brand.css", media_type="text/css")


@app.get("/demo-shop")
def demo_shop():
    return FileResponse(SOURCE_FILES / "shop.html", media_type="text/html")


@app.get("/demo-shop/assets/{name}")
def shop_photo(name: str):
    if name not in {"notebook.png", "tote.png"}:
        raise HTTPException(404, "Photo not found.")
    return FileResponse(SOURCE_FILES / "shop-assets" / name, media_type="image/png")


@app.get("/api/examples")
def examples():
    return [
        {"name": file.name, "source": file.read_text(encoding="utf-8"), "description": bundled_description(file.name)[0]}
        for file in sorted((SOURCE_FILES / "examples").glob("*.py"))
    ]


@app.post("/api/scripts/describe")
def describe_scripts(upload: ScriptSet):
    return [inspect_script(script) for script in upload.scripts]


@app.get("/api/examples/{name}")
def example_file(name: str):
    path = SOURCE_FILES / "examples" / name
    if not SCRIPT_NAME.fullmatch(name) or not path.is_file():
        raise HTTPException(404, "Example not found.")
    return FileResponse(path, media_type="text/x-python", filename=name)


@app.get("/api/example-batches")
def example_batches():
    return [{"id": key, "name": name, "files": files} for key, (name, files) in EXAMPLE_BATCHES.items()]


@app.get("/healthz")
def health():
    return {"status": "ok"}


@app.post("/api/runs", status_code=202)
def create_run(run: RunRequest):
    run_id = f"run-{uuid4().hex}"
    submit_job(run_id, run.check)
    return {"id": run_id}


def submit_job(run_id, check, record_video=False):
    labels = {"app.kubernetes.io/name": "browser-demo-worker", "check": check}
    args = [run_id, check] + (["--video"] if record_video else [])
    job = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"name": run_id, "labels": labels},
        "spec": {
            "backoffLimit": 0,
            "activeDeadlineSeconds": 60,
            "template": {
                "metadata": {"labels": labels},
                "spec": {
                    "restartPolicy": "Never",
                    "automountServiceAccountToken": False,
                    "securityContext": {"runAsUser": 1000, "runAsGroup": 1000, "fsGroup": 1000},
                    "containers": [
                        {
                            "name": "worker",
                            "image": WORKER_IMAGE,
                            "imagePullPolicy": WORKER_IMAGE_PULL_POLICY,
                            "args": args,
                            "env": [{"name": "DEMO_BASE_URL", "value": "http://browser-demo-api:8000/demo-shop"}],
                            "securityContext": {"allowPrivilegeEscalation": False},
                            "resources": {
                                "requests": {"cpu": "100m", "memory": "256Mi"},
                                "limits": {"cpu": "1", "memory": "768Mi"},
                            },
                            "volumeMounts": [{"name": "artifacts", "mountPath": "/artifacts"}],
                        }
                    ],
                    "volumes": [{"name": "artifacts", "persistentVolumeClaim": {"claimName": "artifacts"}}],
                },
            },
        },
    }
    app.state.jobs.create_namespaced_job(NAMESPACE, job, _request_timeout=5)


@app.post("/api/batches", status_code=202)
def create_batch(batch: BatchRequest):
    names = [script.name for script in batch.scripts]
    if len(set(name.casefold() for name in names)) != len(names):
        raise HTTPException(422, "Use distinct .py filenames.")
    descriptions = [inspect_script(script) for script in batch.scripts]
    for info in descriptions:
        if info["error"]:
            raise HTTPException(422, f'{info["name"]}: {info["error"]}')

    batch_id = f"batch-{uuid4().hex}"
    batch_dir = ARTIFACTS / "batches"
    batch_dir.mkdir(parents=True, exist_ok=True)
    runs = []
    for script, info in zip(batch.scripts, descriptions, strict=True):
        run_id = f"run-{uuid4().hex}"
        folder = ARTIFACTS / run_id
        folder.mkdir()
        (folder / "script.py").write_text(script.source.lstrip("\ufeff"), encoding="utf-8")
        runs.append({"id": run_id, "name": script.name, "description": info["description"]})

    created_at = datetime.now(UTC)
    write_json(batch_dir / f"{batch_id}.json", {
        "id": batch_id, "name": batch.name.strip() or f"Batch {created_at:%Y-%m-%d %H:%M UTC}",
        "created_at": created_at.isoformat(), "record_video": batch.record_video, "runs": runs,
    })
    for run in runs:
        try:
            submit_job(run["id"], "script", batch.record_video)
        except Exception:
            logging.getLogger(__name__).exception("Could not submit %s", run["id"])
            write_json(ARTIFACTS / run["id"] / "submission.json", {
                "message": "The API could not confirm that Kubernetes accepted this Job.",
            })
    return {"id": batch_id}


def describe_run(job, pod):
    run_id = job.metadata.name
    status = "Running" if pod and pod.status.phase == "Running" else "Pending"
    message = None
    conditions = job.status.conditions if job.status else None
    for condition in conditions or []:
        if condition.status == "True" and condition.type in {"Complete", "Failed"}:
            status = "Succeeded" if condition.type == "Complete" else "Failed"
            message = condition.message if status == "Failed" else None
            break

    folder = ARTIFACTS / run_id
    try:
        result = json.loads((folder / "result.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        result = {}

    container = next(iter(pod.status.container_statuses or []), None) if pod else None
    state = container.state if container else None
    execution = (state.terminated or state.running) if state else None

    return {
        "id": run_id,
        "check": job.metadata.labels["check"],
        "created_at": job.metadata.creation_timestamp,
        "status": status,
        "message": result.get("message") or message,
        "pod": pod.metadata.name if pod else None,
        "started_at": execution.started_at if execution else None,
        "finished_at": state.terminated.finished_at if state and state.terminated else None,
        "screenshot": f"/api/runs/{run_id}/screenshot" if (folder / "screenshot.png").is_file() else None,
        "log": f"/api/runs/{run_id}/log" if (folder / "run.log").is_file() else None,
        "video": f"/api/runs/{run_id}/video" if (folder / "video.webm").is_file() else None,
    }


def cluster_runs():
    jobs = app.state.jobs.list_namespaced_job(NAMESPACE, label_selector=WORKER_LABEL, _request_timeout=5).items
    pods = app.state.pods.list_namespaced_pod(NAMESPACE, label_selector=WORKER_LABEL, _request_timeout=5).items
    worker_pods = {
        pod.metadata.labels.get("batch.kubernetes.io/job-name"): pod
        for pod in sorted(pods, key=lambda pod: pod.metadata.creation_timestamp)
    }
    return {job.metadata.name: describe_run(job, worker_pods.get(job.metadata.name)) for job in jobs}


@app.get("/api/runs")
def list_runs():
    return sorted(cluster_runs().values(), key=lambda run: run["created_at"], reverse=True)[:20]


@app.get("/api/batches")
def list_batches():
    files = []
    for path in (ARTIFACTS / "batches").glob("batch-*.json"):
        try:
            files.append((path.stat().st_mtime, path))
        except FileNotFoundError:
            continue
    runs = cluster_runs()
    recent = []
    for _, path in sorted(files, key=lambda item: item[0], reverse=True)[:30]:
        try:
            batch = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            continue
        update_batch_runs(batch, runs)
        recent.append(batch)
    return recent


def update_batch_runs(batch, runs):
    age = (datetime.now(UTC) - datetime.fromisoformat(batch["created_at"])).total_seconds()
    for run in batch["runs"]:
        if "description" not in run:
            run["description"] = historical_description(run["id"], run["name"])
        details = runs.get(run["id"])
        if details:
            run.update(details)
            continue
        try:
            error = json.loads((ARTIFACTS / run["id"] / "submission.json").read_text(encoding="utf-8"))
        except FileNotFoundError:
            if age > 60:
                run.update(status="Failed", message="Kubernetes did not report a Job for this check.")
            else:
                run["status"] = "Pending"
        else:
            run.update(status="Failed", **error)


@app.delete("/api/batches/{batch_id}")
def delete_batch(batch_id: str):
    if not BATCH_ID.fullmatch(batch_id):
        raise HTTPException(404, "Batch not found.")
    path = ARTIFACTS / "batches" / f"{batch_id}.json"
    archived = ARTIFACTS / "history-archive" / "deleted-batches" / path.name
    try:
        batch = json.loads(path.read_text(encoding="utf-8"))
        update_batch_runs(batch, cluster_runs())
        if any(run["status"] not in {"Succeeded", "Failed"} for run in batch["runs"]):
            raise HTTPException(409, "Wait for the batch to finish before deleting it.")
        archived.parent.mkdir(parents=True, exist_ok=True)
        path.rename(archived)
    except FileNotFoundError:
        if not archived.is_file():
            raise HTTPException(404, "Batch not found.") from None
    return {"id": batch_id}


@app.get("/api/runs/{run_id}/screenshot")
def screenshot(run_id: str, inline: bool = False):
    return artifact(run_id, "screenshot.png", "image/png", inline)


@app.get("/api/runs/{run_id}/log")
def run_log(run_id: str):
    return artifact(run_id, "run.log", "text/plain", True)


@app.get("/api/runs/{run_id}/video")
def run_video(run_id: str):
    return artifact(run_id, "video.webm", "video/webm", True)


def artifact(run_id, name, media_type, inline):
    if not RUN_ID.fullmatch(run_id):
        raise HTTPException(status_code=404, detail="Artifact is unavailable.")
    path = ARTIFACTS / run_id / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Artifact is unavailable.")
    return FileResponse(
        path, media_type=media_type, filename=f"{run_id}-{name}",
        content_disposition_type="inline" if inline else "attachment",
    )
