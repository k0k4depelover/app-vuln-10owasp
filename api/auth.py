import os

import jwt
from dotenv import load_dotenv
from fastapi import Header, HTTPException

load_dotenv()


SECRET_KEY = os.getenv("SECRET_KEY")
# =========================================================
# Auth
# =========================================================


def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Falta token")

    token = authorization.replace("Bearer ", "")
    try:
        # 🔴 Sin `algorithms=[...]` -> acepta alg="none".
        # Con SECRET_KEY vacío además, HS256 también es forjable.
        payload = jwt.decode(token, SECRET_KEY, options={"verify_signature": False})
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido")

    return payload
