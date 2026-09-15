"""
Voxevia - Hospital AI Voice Agent

Main FastAPI application entry point.

Run locally:

    python -m uvicorn app.main:app --reload --port 8000

Swagger documentation:

    http://127.0.0.1:8000/docs
"""

from fastapi import FastAPI

from app.api.routes_calls import router as calls_router
from app.api.routes_health import router as health_router
from app.api.routes_hospital import router as hospital_router
from app.api.routes_departments import router as departments_router
from app.api.routes_doctors import router as doctors_router
from app.api.routes_schedules import router as schedules_router
from app.api.routes_slots import router as slots_router
from app.api.routes_patients import router as patients_router
from app.api.routes_appointments import router as appointments_router


# ============================================================
# CREATE FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="Voxevia Hospital Voice AI Platform",
    description="AI voice assistant platform for a hospital.",
    version="0.1.0",
)


# ============================================================
# ROOT ENDPOINT
# ============================================================

@app.get("/", tags=["System"])
def root():
    return {
        "status": "ok",
        "service": "Voxevia Hospital Voice AI Platform",
        "version": "0.1.0",
        "mode": "inbound",
    }


# ============================================================
# REGISTER API ROUTES
# ============================================================

app.include_router(health_router)
app.include_router(calls_router)
app.include_router(hospital_router)
app.include_router(departments_router)
app.include_router(doctors_router)
app.include_router(schedules_router)
app.include_router(slots_router)
app.include_router(patients_router)
app.include_router(appointments_router)