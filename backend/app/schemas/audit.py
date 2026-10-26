"""AuditEvent Pydantic schemas."""

import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class AuditEventRead(BaseModel):
    """Audit event representation for compliance reporting."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_user_id: uuid.UUID | None = None
    action: str
    resource_id: str | None = None
    resource_type: str | None = None
    outcome: str
    details: str | None = None
    ip_address: str | None = None
    request_id: str | None = None
    timestamp: datetime
