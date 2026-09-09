"""
API DE PRÁCTICA — VULNERABLE A PROPÓSITO
==========================================
Sistema de gestión de multas con "autenticación" y pagos mock de Stripe.

Contiene intencionalmente 3 vulnerabilidades del OWASP API Top 10:

  1. Broken Authentication
     - SECRET_KEY vacío
     - jwt.decode sin `algorithms=[...]` explícito -> acepta alg="none"
     - Tokens sin `exp` (nunca expiran)
     - /auth/login sin rate limiting -> brute force libre

  2. Broken Object Level Authorization (BOLA)
     - GET /fines/{fine_id} no valida que la multa pertenezca al usuario
     - GET /invoices/{invoice_id} tampoco

  3. Broken Object Property Level Authorization (BOPLA)
     - POST /fines/{fine_id}/pay confía en el campo "amount" que
       manda el cliente, en vez de usar fine["amount"] del servidor
       (mass assignment sobre el monto a cobrar)

NO USAR EN PRODUCCIÓN. Código para ejercicio de pentesting/fix propio.

Corre con:
    uvicorn main:app --reload
"""

import uuid
from datetime import datetime
from typing import Annotated

import jwt
import pymysql
from fastapi import Dependency, Depends, FastAPI, Header, HTTPException

# Úsala como tipo:
DbDependency = Annotated[MySQLConnectionAbstract, Depends(get_db)]
from pydantic import BaseModel

from database import get_db

app = FastAPI(title="Multas API (VULNERABLE)")

# =========================================================
# 🔴 VULNERABILIDAD #1: Broken Authentication
# =========================================================
SECRET_KEY = ""  # <-- secreto vacío. Cualquiera puede firmar tokens "válidos".

# =========================================================
# "Base de datos" en memoria — PLACEHOLDER
# Reemplaza estas funciones por queries reales a tu DB.
# Ver README.md para el esquema de tablas sugerido.
# =========================================================

db_dependency = Annotated[pymysql.connections.Connection, Depends(get_db)]


def get_user_by_username(username: str, db: db_dependency):
    if username == "":
        raise HTTPException(400, "El nombre de usuario no es valido.")

    query = "SELECT * FROM users WHERE username=%s"
    with db.cursor() as cursor:
        user_data = cursor.execute(query, username)
    return user_data


def get_fine_by_id(fine_id: int, db: db_dependency):
    if fine_id <= 0:
        raise HTTPException(400, "El id no es valido")
    query = "SELECT * FROM fines WHERE id=%s"
    with db.cursor() as cursor:
        fine_data = cursor.execute(query, fine_id)
    return fine_data


# =========================================================
# Modelos
# =========================================================


class LoginRequest(BaseModel):
    username: str
    password: str


class PayRequest(BaseModel):
    # 🔴 BOPLA: el cliente decide cuánto paga
    amount: float
    card_number: str = "4242424242424242"  # tarjeta de prueba mock-stripe


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


@app.post("/auth/login")
def login(data: LoginRequest):
    # 🔴 Sin rate limiting: fuerza bruta sin restricción
    user = get_user_by_username(data.username)
    if not user or user["password"] != data.password:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    # 🔴 Token sin "exp" -> nunca expira
    token = jwt.encode(
        {"user_id": user["id"], "username": user["username"], "role": user["role"]},
        SECRET_KEY,
        algorithm="HS256",
    )
    return {"access_token": token, "token_type": "bearer"}


# =========================================================
# 🔴 VULNERABILIDAD #2: BOLA
# =========================================================


@app.get("/fines/{fine_id}")
def get_fine(fine_id: int, authorization: str = Header(None)):
    current_user = get_current_user(authorization)
    fine = get_fine_by_id(fine_id)
    if not fine:
        raise HTTPException(status_code=404, detail="Multa no encontrada")

    # 🔴 No verifica fine["user_id"] == current_user["user_id"]
    return fine


# =========================================================
# 🔴 VULNERABILIDAD #3: BOPLA (mass assignment) + BOLA heredado
# =========================================================


@app.post("/fines/{fine_id}/pay")
def pay_fine(fine_id: int, data: PayRequest, authorization: str = Header(None)):
    current_user = get_current_user(authorization)
    fine = get_fine_by_id(fine_id)
    if not fine:
        raise HTTPException(status_code=404, detail="Multa no encontrada")

    # 🔴 No valida ownership de la multa (BOLA)
    # 🔴 Mock de Stripe: "cobra" lo que el cliente diga, no lo real (BOPLA)
    stripe_charge_id = f"ch_mock_{uuid.uuid4().hex[:16]}"

    invoice_id = len(MOCK_INVOICES) + 1
    invoice = {
        "id": invoice_id,
        "fine_id": fine_id,
        "user_id": current_user["user_id"],
        "amount": data.amount,  # 🔴 monto controlado por el cliente
        "stripe_charge_id": stripe_charge_id,
        "created_at": datetime.utcnow().isoformat(),
    }
    MOCK_INVOICES[invoice_id] = invoice
    fine["paid"] = True  # 🔴 se marca pagada sin validar el monto real

    return {"message": "Pago procesado", "invoice": invoice}


@app.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: int, authorization: str = Header(None)):
    current_user = get_current_user(authorization)
    invoice = MOCK_INVOICES.get(invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    # 🔴 BOLA otra vez: no valida invoice["user_id"] == current_user["user_id"]
    return invoice


@app.get("/")
def root():
    return {"status": "API de multas corriendo (VERSIÓN VULNERABLE)"}
