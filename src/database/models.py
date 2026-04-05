"""
Database Models

This module defines data models for database operations with proper
validation and type safety.
"""

import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

from pydantic import BaseModel, Field, validator, EmailStr


class TicketStatus(str, Enum):
    """Valid ticket statuses."""
    OPEN = "Open"
    ASSIGNED = "Assigned"
    WORK_IN_PROGRESS = "WorkInProgress"
    RESOLVED = "Resolved"
    COMPLETED = "Completed"
    ESCALATED = "Escalated"
    HR = "HR"


class ApprovalStatus(str, Enum):
    """Valid approval statuses."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class NotificationStatus(str, Enum):
    """Valid notification statuses."""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    RETRY = "retry"


class DatabaseDatabaseBaseModel(DatabaseBaseModel):
    """Base model with common configuration."""

    class Config:
        """Pydantic model configuration."""
        use_enum_values = True
        validate_assignment = True
        str_strip_whitespace = True


class TicketModel(DatabaseDatabaseBaseModel):
    """Ticket data model with validation."""

    ticket_id: str = Field(..., min_length=1, max_length=50)
    subject: str = Field(..., min_length=5, max_length=255)
    description: str = Field(..., min_length=10, max_length=10000)
    submitter: str = Field(..., min_length=2, max_length=100)
    submitter_email: EmailStr
    phone_number: str = Field("", max_length=20)
    status: TicketStatus = TicketStatus.OPEN
    ai_resolution: str = Field("", max_length=10000)
    similar_ticket_ids: List[str] = Field(default_factory=list)
    assigned_to: str = Field("", max_length=50)
    classification_json: Dict[str, Any] = Field(default_factory=dict)
    routing_json: Dict[str, Any] = Field(default_factory=dict)
    response_json: Optional[Dict[str, Any]] = None
    processed_at: datetime
    processing_time_ms: float = Field(ge=0)
    created_at: datetime
    updated_at: datetime

    @validator('similar_ticket_ids', pre=True)
    def parse_similar_tickets(cls, v):
        """Parse similar ticket IDs from JSON string if needed."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return []
        return v or []

    @validator('classification_json', 'routing_json', 'response_json', pre=True)
    def parse_json_fields(cls, v):
        """Parse JSON fields from string if needed."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return {} if v != "" else {}
        return v or {}

    def to_db_dict(self) -> Dict[str, Any]:
        """Convert model to database dictionary format."""
        data = self.dict()

        # Convert lists/dicts to JSON strings for database storage
        data['similar_ticket_ids'] = json.dumps(self.similar_ticket_ids)
        data['classification_json'] = json.dumps(self.classification_json)
        data['routing_json'] = json.dumps(self.routing_json)

        if self.response_json is not None:
            data['response_json'] = json.dumps(self.response_json)

        # Convert datetime objects to ISO strings
        data['processed_at'] = self.processed_at.isoformat()
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()

        return data

    @classmethod
    def from_db_row(cls, row) -> 'TicketModel':
        """Create model from database row."""
        data = dict(row)

        # Parse datetime fields
        for field in ['processed_at', 'created_at', 'updated_at']:
            if data.get(field):
                data[field] = datetime.fromisoformat(data[field])

        # Parse JSON fields
        for field in ['similar_ticket_ids', 'classification_json', 'routing_json', 'response_json']:
            if data.get(field):
                try:
                    data[field] = json.loads(data[field])
                except json.JSONDecodeError:
                    data[field] = [] if field == 'similar_ticket_ids' else {}

        return cls(**data)


class ApprovalModel(DatabaseBaseModel):
    """Approval data model with validation."""

    ticket_id: str = Field(..., min_length=1, max_length=50)
    status: ApprovalStatus = ApprovalStatus.PENDING
    ai_category: str = Field(..., min_length=1, max_length=100)
    ai_confidence: float = Field(ge=0.0, le=1.0)
    ai_response: str = Field(..., min_length=1)
    assigned_queue: str = Field(..., min_length=1, max_length=100)
    created_at: datetime
    updated_at: datetime
    reviewed_by: str = Field("", max_length=50)
    reviewer_notes: str = Field("", max_length=1000)
    final_response: str = Field("", max_length=10000)

    def to_db_dict(self) -> Dict[str, Any]:
        """Convert model to database dictionary format."""
        data = self.dict()

        # Convert datetime objects to ISO strings
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()

        return data

    @classmethod
    def from_db_row(cls, row) -> 'ApprovalModel':
        """Create model from database row."""
        data = dict(row)

        # Parse datetime fields
        for field in ['created_at', 'updated_at']:
            if data.get(field):
                data[field] = datetime.fromisoformat(data[field])

        return cls(**data)


class ApprovalEventModel(DatabaseBaseModel):
    """Approval event data model for audit trail."""

    id: Optional[int] = None
    ticket_id: str = Field(..., min_length=1, max_length=50)
    event_type: str = Field(..., regex=r'^(created|approved|rejected|modified)$')
    actor: str = Field(..., min_length=1, max_length=50)
    details: str = Field("", max_length=1000)
    created_at: datetime

    def to_db_dict(self) -> Dict[str, Any]:
        """Convert model to database dictionary format."""
        data = self.dict(exclude={'id'} if self.id is None else set())
        data['created_at'] = self.created_at.isoformat()
        return data

    @classmethod
    def from_db_row(cls, row) -> 'ApprovalEventModel':
        """Create model from database row."""
        data = dict(row)
        if data.get('created_at'):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        return cls(**data)


class MetricsModel(DatabaseBaseModel):
    """Metrics data model for analytics."""

    ticket_id: str = Field(..., min_length=1, max_length=50)
    created_at: datetime
    first_response_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    category: str = Field(..., min_length=1, max_length=100)
    queue: str = Field(..., min_length=1, max_length=100)
    was_auto_resolved: bool = False

    def to_db_dict(self) -> Dict[str, Any]:
        """Convert model to database dictionary format."""
        data = self.dict()

        # Convert datetime objects to ISO strings
        data['created_at'] = self.created_at.isoformat()

        if self.first_response_at:
            data['first_response_at'] = self.first_response_at.isoformat()

        if self.resolved_at:
            data['resolved_at'] = self.resolved_at.isoformat()

        # Convert boolean to integer for SQLite
        data['was_auto_resolved'] = int(self.was_auto_resolved)

        return data

    @classmethod
    def from_db_row(cls, row) -> 'MetricsModel':
        """Create model from database row."""
        data = dict(row)

        # Parse datetime fields
        for field in ['created_at', 'first_response_at', 'resolved_at']:
            if data.get(field):
                data[field] = datetime.fromisoformat(data[field])

        # Convert integer back to boolean
        if 'was_auto_resolved' in data:
            data['was_auto_resolved'] = bool(data['was_auto_resolved'])

        return cls(**data)


class EmailNotificationModel(DatabaseBaseModel):
    """Email notification data model."""

    id: Optional[int] = None
    ticket_id: str = Field(..., min_length=1, max_length=50)
    recipient: EmailStr
    subject: str = Field(..., min_length=1, max_length=255)
    body_preview: str = Field("", max_length=500)
    status: NotificationStatus = NotificationStatus.PENDING
    sent_at: Optional[datetime] = None
    error_message: str = Field("", max_length=1000)
    created_at: datetime

    def to_db_dict(self) -> Dict[str, Any]:
        """Convert model to database dictionary format."""
        data = self.dict(exclude={'id'} if self.id is None else set())

        # Convert datetime objects to ISO strings
        data['created_at'] = self.created_at.isoformat()

        if self.sent_at:
            data['sent_at'] = self.sent_at.isoformat()

        return data

    @classmethod
    def from_db_row(cls, row) -> 'EmailNotificationModel':
        """Create model from database row."""
        data = dict(row)

        # Parse datetime fields
        for field in ['created_at', 'sent_at']:
            if data.get(field):
                data[field] = datetime.fromisoformat(data[field])

        return cls(**data)


class UserModel(DatabaseBaseModel):
    """User data model."""

    username: str = Field(..., min_length=1, max_length=50)
    display_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    role: str = Field(..., regex=r'^(admin|engineer)$')
    is_active: bool = True
    created_at: datetime
    last_login: Optional[datetime] = None

    def to_db_dict(self) -> Dict[str, Any]:
        """Convert model to database dictionary format."""
        data = self.dict()

        # Convert datetime objects to ISO strings
        data['created_at'] = self.created_at.isoformat()

        if self.last_login:
            data['last_login'] = self.last_login.isoformat()

        # Convert boolean to integer for SQLite
        data['is_active'] = int(self.is_active)

        return data

    @classmethod
    def from_db_row(cls, row) -> 'UserModel':
        """Create model from database row."""
        data = dict(row)

        # Parse datetime fields
        for field in ['created_at', 'last_login']:
            if data.get(field):
                data[field] = datetime.fromisoformat(data[field])

        # Convert integer back to boolean
        if 'is_active' in data:
            data['is_active'] = bool(data['is_active'])

        return cls(**data)


class AuditLogModel(DatabaseBaseModel):
    """Audit log data model for security tracking."""

    id: Optional[int] = None
    user_id: str = Field(..., min_length=1, max_length=50)
    action: str = Field(..., min_length=1, max_length=100)
    resource_type: str = Field(..., min_length=1, max_length=50)
    resource_id: Optional[str] = Field(None, max_length=50)
    details: str = Field("", max_length=1000)
    ip_address: str = Field("", max_length=45)
    user_agent: str = Field("", max_length=500)
    created_at: datetime

    def to_db_dict(self) -> Dict[str, Any]:
        """Convert model to database dictionary format."""
        data = self.dict(exclude={'id'} if self.id is None else set())
        data['created_at'] = self.created_at.isoformat()
        return data

    @classmethod
    def from_db_row(cls, row) -> 'AuditLogModel':
        """Create model from database row."""
        data = dict(row)
        if data.get('created_at'):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        return cls(**data)