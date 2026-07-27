import hashlib
import hmac

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field

from app.supabase_client import SUPABASE_URL, HEADERS

router = APIRouter()

MASTER_EMAIL = "anderson@cremeni.com.br"
MASTER_UID = "14737212-032c-4b69-a6cb-a6fe80e8cf11"
ACTIVATION_HASH = "ef394e2d406cceaff098b4df1385790912708774a73a5badf640e4f56ec58cea"


class MasterFirstAccessRequest(BaseModel):
    email: EmailStr
    activation_code: str = Field(min_length=20, max_length=100)
    password: str = Field(min_length=10, max_length=128)


@router.post("/auth/master/first-access")
def master_first_access(payload: MasterFirstAccessRequest):
    if payload.email.lower().strip() != MASTER_EMAIL:
        raise HTTPException(status_code=403, detail="Dados de ativação inválidos")

    supplied_hash = hashlib.sha256(payload.activation_code.strip().encode("utf-8")).hexdigest()
    if not hmac.compare_digest(supplied_hash, ACTIVATION_HASH):
        raise HTTPException(status_code=403, detail="Dados de ativação inválidos")

    user_url = f"{SUPABASE_URL}/auth/v1/admin/users/{MASTER_UID}"
    current = requests.get(user_url, headers=HEADERS, timeout=15)
    if current.status_code >= 400:
        raise HTTPException(status_code=502, detail="Não foi possível validar o usuário Master")

    user_data = current.json()
    metadata = user_data.get("user_metadata") or {}
    if metadata.get("master_bootstrap_completed") is True:
        raise HTTPException(status_code=409, detail="O primeiro acesso Master já foi concluído")

    metadata.update({
        "master_bootstrap_completed": True,
        "tipo_usuario": "master",
        "is_owner": True,
    })

    update = requests.put(
        user_url,
        headers={**HEADERS, "Content-Type": "application/json"},
        json={
            "password": payload.password,
            "email_confirm": True,
            "user_metadata": metadata,
        },
        timeout=20,
    )

    if update.status_code >= 400:
        raise HTTPException(status_code=502, detail="Não foi possível concluir a ativação Master")

    return {"status": "master_activated"}
