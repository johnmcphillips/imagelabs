from typing import List, Optional
from models import Job
from redis_client import redis_client

PREFIX = "job:"

def job_key(job_id: str) -> str:
    return f"{PREFIX}{job_id}"

def create_job(job: Job) -> None:
    redis_client.set(
        job_key(job.id),
        job.model_dump_json(),
        ex=3600
        )

def load_job(job_id: str) -> Optional[Job]:
    data = redis_client.get(job_key(job_id))
    if data is None:
        return None
    return Job.model_validate_json(data)

def list_jobs() -> List[Job]:
    jobs: List[Job] = []
    for key in redis_client.scan_iter(f"{PREFIX}*"):
        data = redis_client.get(key)
        if data:
            job = Job.model_validate_json(data)
            jobs.append(job)
    return jobs
