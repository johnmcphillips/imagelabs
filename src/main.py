import shutil
import logging
import time
from datetime import datetime, timezone
from uuid import uuid4
from pathlib import Path
from typing import Dict

from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Response
from fastapi.responses import FileResponse
from starlette import status
from PIL import Image
from models import Job, JobStatus
from jobs import create_job, load_job, list_jobs

logger = logging.getLogger("thumbnail-api")
logging.basicConfig(level=logging.INFO)

# Storage
BASE_PATH = Path("/data")
UPLOAD_PATH = BASE_PATH / "uploads"
THUMBNAIL_PATH = BASE_PATH / "thumbnails"

UPLOAD_PATH.mkdir(parents=True, exist_ok=True)
THUMBNAIL_PATH.mkdir(parents=True, exist_ok=True)

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
        logger.info(f"Job {job_id} completed in {processing_time:.2f} seconds.")

    except Exception as e:
        job.status = JobStatus.FAILED
        create_job(job)
        jobs_failed.inc()
        logger.exception(f"Job {job_id} failed: {e}")


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

    if background_tasks is not None:
        background_tasks.add_task(process_image, job_id)

    return {"job_id": job_id}

@app.get("/thumbnails/{job_id}")
def get_thumbnail(job_id: str) -> FileResponse:
    job = load_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
            )

    if job.status != JobStatus.SUCCEEDED or not job.output_file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Thumbnail not available"
            )

    output_path = THUMBNAIL_PATH / job.output_file
    return FileResponse(output_path, media_type="image/png", filename=job.output_file)

@app.get("/jobs")
def get_all_jobs() -> Dict[str, Job]:
    jobs = list_jobs()
    return {job.id: job for job in jobs}

@app.get("/jobs/{job_id}/status", response_model=Job)
def get_job_status(job_id: str) -> Job:
    job = load_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
            )
    return job
