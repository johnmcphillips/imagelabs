import threading
import shutil
from datetime import datetime, timezone
from uuid import uuid4
from pathlib import Path
from enum import Enum
from typing import Optional, Dict

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from starlette import status
from PIL import Image
from pydantic import BaseModel, Field

# Storage
BASE_PATH = Path("/data")
UPLOAD_PATH = BASE_PATH / "uploads"
THUMBNAIL_PATH = BASE_PATH / "thumbnails"

UPLOAD_PATH.mkdir(parents=True, exist_ok=True)
THUMBNAIL_PATH.mkdir(parents=True, exist_ok=True)

# Jobs store
class JobStatus(str, Enum):
    PROCESSING = "Processing"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"

class Job(BaseModel):
    id: str
    status: JobStatus
    input_file: str
    output_file: Optional[str] = None
    time_created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

JOBS: Dict[str, Job] = {}
JOBS_LOCK = threading.Lock()

# Worker
def process_image(job_id: str):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job:
        print(f"Job {job_id} not found")
        return
    try:
        input_path = UPLOAD_PATH / job.input_file
        output_path = THUMBNAIL_PATH / f"thumb_{job.input_file}"

        with Image.open(input_path) as img:
            img.thumbnail((100, 100))
            img.save(output_path)

        with JOBS_LOCK:
            job.status = JobStatus.SUCCEEDED
            job.output_file = output_path.name
        print(f"Job {job_id} completed successfully")

    except Exception as e:
        with JOBS_LOCK:
            job.status = JobStatus.FAILED
        print(f"Job {job_id} failed: {e}")


# FastAPI
app = FastAPI(title="Image Thumbnail Service", version="0.1.0")

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

    with JOBS_LOCK:
        JOBS[job_id] = job

    if background_tasks is not None:
        background_tasks.add_task(process_image, job_id)
    return {"job_id": job_id}

@app.get("/thumbnails/{job_id}")
def get_thumbnail(job_id: str) -> FileResponse:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
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
    with JOBS_LOCK:
        return dict(JOBS)

@app.get("/jobs/{job_id}/status", response_model=Job)
def get_job_status(job_id: str) -> Job:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
            )
    return job
