from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

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
