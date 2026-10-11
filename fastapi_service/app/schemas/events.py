from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ApplicationStatusIn(BaseModel):
    """Подія від Django: змінився статус заявки."""
    application_id: int = Field(gt=0)
    candidate_id: int = Field(gt=0)
    vacancy_id: int = Field(gt=0)
    status: str = Field(min_length=1, max_length=16)
    status_label: str = ''
    vacancy_title: str = ''


class ApplicationEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    application_id: int
    candidate_id: int
    vacancy_id: int
    vacancy_title: str
    status: str
    status_label: str
    created_at: datetime


class StatusAck(BaseModel):
    stored: bool = True
    delivered_to: int = 0
