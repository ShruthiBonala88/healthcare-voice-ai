"""
Appointment API.

Handles creating and retrieving hospital appointments.
"""

from datetime import date, time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.data.supabase_client import get_supabase


router = APIRouter(
    prefix="/appointments",
    tags=["Appointments"],
)


class AppointmentCreate(BaseModel):
    patient_id: str
    doctor_id: str
    slot_id: str
    reason: str | None = None


@router.post("")
def create_appointment(appointment: AppointmentCreate):
    """
    Book an appointment using an available appointment slot.
    """

    try:
        supabase = get_supabase()

        # 1. Get the slot
        slot_response = (
            supabase
            .table("appointment_slots")
            .select("*")
            .eq("id", appointment.slot_id)
            .limit(1)
            .execute()
        )

        if not slot_response.data:
            raise HTTPException(
                status_code=404,
                detail="Appointment slot not found.",
            )

        slot = slot_response.data[0]

        # 2. Make sure the slot belongs to the selected doctor
        if slot["doctor_id"] != appointment.doctor_id:
            raise HTTPException(
                status_code=400,
                detail="Appointment slot does not belong to this doctor.",
            )

        # 3. Make sure the slot is available
        if slot["status"] != "available":
            raise HTTPException(
                status_code=409,
                detail="Appointment slot is no longer available.",
            )

        # 4. Check patient exists
        patient_response = (
            supabase
            .table("patients")
            .select("id")
            .eq("id", appointment.patient_id)
            .limit(1)
            .execute()
        )

        if not patient_response.data:
            raise HTTPException(
                status_code=404,
                detail="Patient not found.",
            )

        # 5. Get doctor's department
        doctor_response = (
            supabase
            .table("doctors")
            .select("id, department_id")
            .eq("id", appointment.doctor_id)
            .limit(1)
            .execute()
        )

        if not doctor_response.data:
            raise HTTPException(
                status_code=404,
                detail="Doctor not found.",
            )

        doctor = doctor_response.data[0]

        # 6. Create appointment
        appointment_response = (
            supabase
            .table("appointments")
            .insert(
                {
                    "patient_id": appointment.patient_id,
                    "doctor_id": appointment.doctor_id,
                    "department_id": doctor.get("department_id"),
                    "slot_id": appointment.slot_id,
                    "appointment_date": slot["slot_date"],
                    "start_time": slot["start_time"],
                    "end_time": slot["end_time"],
                    "reason": appointment.reason,
                    "status": "scheduled",
                }
            )
            .execute()
        )

        if not appointment_response.data:
            raise HTTPException(
                status_code=500,
                detail="Failed to create appointment.",
            )

        created_appointment = appointment_response.data[0]

        # 7. Mark slot as booked
        slot_response = (
            supabase
            .table("appointment_slots")
            .update(
                {
                    "status": "booked",
                }
            )
            .eq("id", appointment.slot_id)
            .eq("status", "available")
            .execute()
        )

        if not slot_response.data:
            raise HTTPException(
                status_code=409,
                detail="Slot could not be booked. It may have already been taken.",
            )

        return {
            "status": "success",
            "message": "Appointment booked successfully.",
            "appointment": created_appointment,
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create appointment: {exc}",
        )


@router.get("")
def get_appointments(
    patient_id: str | None = None,
    doctor_id: str | None = None,
    appointment_date: date | None = None,
):
    """
    Return appointments with optional filters.
    """

    try:
        supabase = get_supabase()

        query = (
            supabase
            .table("appointments")
            .select(
                """
                *,
                patients(id, full_name, phone),
                doctors(id, name, specialization),
                departments(id, name)
                """
            )
        )

        if patient_id:
            query = query.eq(
                "patient_id",
                patient_id,
            )

        if doctor_id:
            query = query.eq(
                "doctor_id",
                doctor_id,
            )

        if appointment_date:
            query = query.eq(
                "appointment_date",
                appointment_date.isoformat(),
            )

        response = (
            query
            .order("appointment_date")
            .order("start_time")
            .execute()
        )

        return {
            "status": "ok",
            "appointments": response.data,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch appointments: {exc}",
        )


@router.get("/{appointment_id}")
def get_appointment(appointment_id: str):
    """
    Return one appointment.
    """

    try:
        supabase = get_supabase()

        response = (
            supabase
            .table("appointments")
            .select(
                """
                *,
                patients(id, full_name, phone),
                doctors(id, name, specialization),
                departments(id, name)
                """
            )
            .eq("id", appointment_id)
            .limit(1)
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=404,
                detail="Appointment not found.",
            )

        return {
            "status": "ok",
            "appointment": response.data[0],
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch appointment: {exc}",
        )