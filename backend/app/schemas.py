"""Shared Pydantic schemas used across multiple routers."""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class AuditEventOut(BaseModel):
    id: str
    package_id: Optional[str] = None
    actor_user_id: Optional[str] = None
    action: str
    before_state: Optional[Any] = None
    after_state: Optional[Any] = None
    created_at: datetime

    model_config = {"from_attributes": True}
