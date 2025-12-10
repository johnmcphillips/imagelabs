import html
import shutil
import logging
import time
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from uuid import uuid4
from pathlib import Path
from typing import Dict

from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Response
from fastapi.responses import FileResponse, HTMLResponse
from starlette import status
from PIL import Image
from models import Job, JobStatus
from jobs import create_job, load_job, list_jobs

# Storage
BASE_PATH = Path("/data")
UPLOAD_PATH = BASE_PATH / "uploads"
THUMBNAIL_PATH = BASE_PATH / "thumbnails"
LOG_PATH = BASE_PATH / "logs"
LOG_FILE = LOG_PATH / "thumbnail-api.log"
UPLOAD_PATH.mkdir(parents=True, exist_ok=True)
THUMBNAIL_PATH.mkdir(parents=True, exist_ok=True)
LOG_PATH.mkdir(parents=True, exist_ok=True)

# Logging
logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
logger = logging.getLogger("thumbnail-api")
logger.setLevel(level=logging.INFO)
logger.propagate = False

if not logger.handlers:
    fileHandler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=2, encoding="utf-8")
    fileHandler.setFormatter(logFormatter)
    logger.addHandler(fileHandler)

    consoleHandler = logging.StreamHandler()
    consoleHandler.setFormatter(logFormatter)
    logger.addHandler(consoleHandler)

def tail_logs(n: int = 200) -> str:
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
            return "".join(lines[-n:])
    except Exception as e:
        logger.error(f"Error reading log file: {e}")
        return "Could not read log file."

# Expose Metrics
jobs_created = Counter(
    "thumbnail_jobs_created_total",
    "Total thumbnail jobs created",
)

jobs_succeeded = Counter(
    "thumbnail_jobs_succeeded_total",
    "Total thumbnail jobs successfully processed",
)

jobs_failed = Counter(
    "thumbnail_jobs_failed_total",
    "Total thumbnail jobs that failed processing",
)

jobs_processing_seconds = Histogram(
    "thumbnail_job_processing_seconds",
    "Time spent processing a thumbnail job in seconds",
)

# Worker
def process_image(job_id: str):
    job = load_job(job_id)
    if not job:
        logger.error(f"Job {job_id} not found.")
        return

    start = time.perf_counter()
    try:
        input_path = UPLOAD_PATH / job.input_file
        output_path = THUMBNAIL_PATH / f"thumb_{job.input_file}"

        with Image.open(input_path) as img:
            img.thumbnail((100, 100))
            img.save(output_path)

        processing_time = time.perf_counter() - start
        jobs_processing_seconds.observe(processing_time)

        job.status = JobStatus.SUCCEEDED
        job.output_file = output_path.name
        create_job(job)
        jobs_succeeded.inc()
        logger.info("job_id=%s processed successfully in %.2f seconds.", job_id, processing_time)

    except Exception as e:
        job.status = JobStatus.FAILED
        create_job(job)
        jobs_failed.inc()
        logger.exception("Job job_id=%s failed: %s", job_id, e)

# FastAPI
app = FastAPI(title="Image Thumbnail Service", version="0.1.0")

@app.get("/metrics", include_in_schema=False)
def metrics():
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)

@app.get("/healthz", include_in_schema=False)
def healthz() -> dict:
    return {"status": "ok"}

@app.post("/thumbnails")
async def create_thumbnail(file: UploadFile = File(...), background_tasks: BackgroundTasks = None) -> dict:
    job_id = str(uuid4())
    input_filename = f"{job_id}_{file.filename}"
    input_path = UPLOAD_PATH / input_filename

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file uploaded"
            )

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Only images are allowed."
            )

    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    job = Job(
        id=job_id,
        status=JobStatus.PROCESSING,
        input_file=input_filename,
        time_created=datetime.now(timezone.utc)
        )

    create_job(job)
    jobs_created.inc()
    logger.info("Created job_id=%s for file=%s", job_id, file.filename)

    if background_tasks is not None:
        background_tasks.add_task(process_image, job_id)

    return {"job_id": job_id}

@app.get("/thumbnails/{job_id}")
def get_thumbnail(job_id: str) -> FileResponse:
    job = load_job(job_id)
    if not job:
        logger.error("Thumbnail for job not found job_id=%s", job_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
            )

    if job.status != JobStatus.SUCCEEDED or not job.output_file:
        logger.error("Thumbnail not available for  job_id=%s status=%s output_file=%s", job_id, job.status, job.output_file)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Thumbnail not available"
            )
    output_path = THUMBNAIL_PATH / job.output_file
    logger.info("Fetching thumbnail for job_id=%s output_file=%s", job_id, job.output_file)
    return FileResponse(output_path, media_type="image/png", filename=job.output_file)

@app.get("/jobs")
def get_all_jobs() -> Dict[str, Job]:
    jobs = list_jobs()
    if not jobs:
        logger.info("No jobs found.")
        return {}
    logger.info("Retrieved %d jobs.", len(jobs))
    return {job.id: job for job in jobs}

@app.get("/jobs/{job_id}/status", response_model=Job)
def get_job_status(job_id: str) -> Job:
    job = load_job(job_id)
    if not job:
        logger.error("Job %s not found.", job_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
            )
    return job

@app.get("/logs", response_class=HTMLResponse, include_in_schema=False)
def logs(n: int = 200):
    log_text = tail_logs(n=n)
    html = f"""
    <html>
    <head>
        <title>Thumbnail Processing Logs</title>
        <meta http-equiv="refresh" content="5">
        <style>
            body {{ font-family: monospace; background-color: #f0f0f0; padding: 20px; }}
            .log-entry {{ margin-bottom: 5px; }}
        </style>
    </head>
    <body>
        <h1>Last {n} Log Entries from {LOG_FILE}</h1>
        <pre style="white-space: pre-wrap; word-break: break-word;">{log_text}</pre>
    </body>
    </html>
    """
    return HTMLResponse(content=html)
