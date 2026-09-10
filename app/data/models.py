"""
Pydantic models mirroring the core Supabase tables. Used for validation
at the tool boundary (input/output of business-layer functions).
"""
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class AppointmentStatus(str, Enum):
    scheduled = "scheduled"
    confirmed = "confirmed"
    cancelled = "cancelled"
    completed = "completed"
    no_show = "no_show"


class Patient(BaseModel):
    id: Optional[UUID] = None
    first_name: str
    last_name: str
    phone_number: str
    email: Optional[EmailStr] = None
    date_of_birth: Optional[str] = None  # ISO date string
    created_at: Optional[datetime] = None


class Department(BaseModel):
    id: Optional[UUID] = None
    name: str
    description: Optional[str] = None


class Doctor(BaseModel):
    id: Optional[UUID] = None
    first_name: str
    last_name: str
    department_id: UUID
    specialty: Optional[str] = None
    bio: Optional[str] = None


class DoctorSchedule(BaseModel):
    id: Optional[UUID] = None
    doctor_id: UUID
    day_of_week: int = Field(ge=0, le=6)  # 0=Monday
    start_time: str  # "09:00"
    end_time: str  # "17:00"
    slot_duration_minutes: int = 30


class AppointmentSlot(BaseModel):
    id: Optional[UUID] = None
    doctor_id: UUID
    start_at: datetime
    end_at: datetime
    is_booked: bool = False


class Appointment(BaseModel):
    id: Optional[UUID] = None
    patient_id: UUID
    doctor_id: UUID
    slot_id: UUID
    status: AppointmentStatus = AppointmentStatus.scheduled
    reason: Optional[str] = None
    created_at: Optional[datetime] = None


class CallSession(BaseModel):
    id: Optional[UUID] = None
    call_sid: str
    caller_phone_number: str
    patient_id: Optional[UUID] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    outcome: Optional[str] = None  # e.g. "booked", "handed_off", "abandoned"


class CallTranscriptTurn(BaseModel):
    id: Optional[UUID] = None
    call_sid: str
    role: str  # "user" | "assistant" | "tool"
    content: str
    created_at: Optional[datetime] = None
