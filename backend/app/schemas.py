from typing import Literal, Optional

from pydantic import BaseModel, Field


class SlideOut(BaseModel):
    id: int
    local_hash: str
    indication: str
    state: str
    risk_score: Optional[float] = None
    risk_flag: Optional[Literal["red", "yellow", "green"]] = None
    priority_override: Optional[float] = None
    has_heatmap: bool = False
    num_patches: Optional[int] = None
    inference_ms: Optional[float] = None
    decision: Optional[str] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row) -> "SlideOut":
        return cls(
            id=row["id"], local_hash=row["local_hash"], indication=row["indication"], state=row["state"],
            risk_score=row["risk_score"], risk_flag=row["risk_flag"], priority_override=row["priority_override"],
            has_heatmap=bool(row["heatmap_path"]), num_patches=row["num_patches"],
            inference_ms=row["inference_ms"], decision=row["decision"], error=row["error"],
            created_at=row["created_at"], updated_at=row["updated_at"],
        )


class EventOut(BaseModel):
    from_state: Optional[str] = None
    to_state: str
    note: Optional[str] = None
    at: str

    @classmethod
    def from_row(cls, row) -> "EventOut":
        return cls(from_state=row["from_state"], to_state=row["to_state"], note=row["note"], at=row["at"])


class IngestOut(BaseModel):
    id: int
    state: str


class ActionIn(BaseModel):
    action: Literal["confirm_malignancy", "mark_benign", "request_biopsy", "reassign_priority"]
    priority: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class CaptureStartIn(BaseModel):
    source: str


class SnapshotIn(BaseModel):
    patient_id: Optional[str] = None
    indication: Literal["Routine", "Urgent"] = "Routine"
