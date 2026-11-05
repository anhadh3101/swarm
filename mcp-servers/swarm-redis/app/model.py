import json
from typing import Any

from pydantic import BaseModel, Field


def task_stream(role: str) -> str:
    return f"tasks:{role}"


class TaskMessage(BaseModel):
    run_id: str
    job_id: str
    payload: str | dict[str, Any] = Field(
        description="JSON string or object; stored as a string in Redis."
    )

    def to_redis_fields(self) -> dict[str, str]:
        if isinstance(self.payload, str):
            payload_str = self.payload
        else:
            payload_str = json.dumps(self.payload)
        return {
            "run_id": self.run_id,
            "job_id": self.job_id,
            "payload": payload_str,
        }
