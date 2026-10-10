from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class TimeEntryCreate(BaseModel):
    client_id: UUID
    project_id: UUID | None = None
    entry_date: date
    start_time: time | None = None
    end_time: time | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    description: str | None = None
    hourly_rate: Decimal = Field(ge=0)
    billable: bool = True

    @model_validator(mode="after")
    def compute_or_validate_duration(self):
        if self.duration_minutes is None:
            if self.start_time and self.end_time:
                start_dt = datetime.combine(date.today(), self.start_time)
                end_dt = datetime.combine(date.today(), self.end_time)
                if end_dt <= start_dt:
                    raise ValueError("end_time must be after start_time")
                self.duration_minutes = int((end_dt - start_dt).total_seconds() // 60)
            else:
                raise ValueError("Provide either duration_minutes, or both start_time and end_time")
        return self


class TimeEntryUpdate(BaseModel):
    project_id: UUID | None = None
    entry_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    description: str | None = None
    hourly_rate: Decimal | None = Field(default=None, ge=0)
    billable: bool | None = None


class TimeEntryOut(BaseModel):
    id: UUID
    client_id: UUID
    project_id: UUID | None
    user_id: UUID
    entry_date: date
    start_time: time | None
    end_time: time | None
    duration_minutes: int
    description: str | None
    hourly_rate: Decimal
    amount: Decimal
    billable: bool
    invoiced_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}  