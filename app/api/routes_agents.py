from fastapi import APIRouter, HTTPException

from app.data.supabase_client import get_supabase

router = APIRouter(
    prefix="/agents",
    tags=["Agents"],
)


@router.get("")
def get_agents():
    try:
        supabase = get_supabase()

        response = (
            supabase
            .table("agents")
            .select(
                "id, tenant_id, name, description, model, voice, language, status, created_at"
            )
            .execute()
        )

        return {
            "status": "ok",
            "agents": response.data,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch agents: {exc}",
        )