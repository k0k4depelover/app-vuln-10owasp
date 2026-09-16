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

CHANGELOG (fix de bug, NO de seguridad):
    - pay_fine() guardaba en invoices.stripe_charge_id un UUID inventado
      (ch_mock_...) generado antes de llamar a Stripe, en vez del ID real
      que devuelve payment_intent.id. Se eliminó el UUID mock y ahora se
      persiste payment_intent.id. Las 3 vulnerabilidades de arriba siguen
      intactas a propósito.
"""

import os
from datetime import datetime
from typing import Annotated

import jwt
import stripe
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from mysql.connector.pooling import PooledMySQLConnection
from pydantic import BaseModel

from database import get_db

load_dotenv()

# 🟡 Por ahora la secret key vive en .env (correcto). Más adelante, como
# ejercicio, la vamos a "filtrar" a propósito para aprender a rotarla.
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

app = FastAPI(title="Multas API (VULNERABLE)")

# =========================================================
# 🔴 VULNERABILIDAD #1: Broken Authentication
# =========================================================
SECRET_KEY = ""  # <-- secreto vacío. Cualquiera puede firmar tokens "válidos".

# =========================================================
# "Base de datos" — queries reales (ver schema en SQL adjunto)
# =========================================================


db_dependency = Annotated[PooledMySQLConnection, Depends(get_db)]


def get_user_by_username(username: str, db: db_dependency):
    if username == "":
        raise HTTPException(400, "El nombre de usuario no es valido.")

    query = "SELECT * FROM users WHERE username=%s"
    with db.cursor(dictionary=True) as cursor:
        cursor.execute(query, (username,))
        user_data = cursor.fetchone()
    return user_data


def get_invoice_by_id(invoice_id: int, db):
    query = "SELECT * FROM invoices WHERE id=%s"
    with db.cursor(dictionary=True) as cursor:
        cursor.execute(query, (invoice_id,))
        return cursor.fetchone()


def mark_fine_as_paid(fine_id, db: db_dependency):
    if fine_id <= 0:
        raise HTTPException(400, "El id no es valido")
    update_query = "UPDATE fines SET paid=TRUE WHERE id=%s"
    with db.cursor(dictionary=True) as cursor:
        cursor.execute(update_query, (fine_id,))
        db.commit()


def insert_invoice(
    fine_id: int,
    user_id: int,
    amount: float,
    stripe_charge_id: str,
    stripe_status,
    db: db_dependency,
):
    if user_id <= 0 or amount < 0 or fine_id < 0:
        raise HTTPException(status_code=400, detail="Valores invalidos para ingresar")

    invoice_insert = (
        "INSERT INTO invoices(fine_id, user_id, amount, stripe_charge_id, stripe_status, created_at) "
        "VALUES(%s, %s, %s, %s, %s, %s)"
    )

    with db.cursor(dictionary=True) as cursor:
        cursor.execute(
            invoice_insert,
            (
                fine_id,
                user_id,
                amount,
                stripe_charge_id,
                stripe_status,
                datetime.now(),
            ),
        )
        db.commit()
        return cursor.lastrowid


# VIEJO CODIGO INSEGURO:


# def get_fine_by_id(fine_id: int, db: db_dependency):
#     if fine_id <= 0:
#         raise HTTPException(400, "El id no es valido")
#     query = "SELECT * FROM fines WHERE id=%s"
#     with db.cursor(dictionary=True) as cursor:
#         cursor.execute(query, (fine_id,))
#         fine_data = cursor.fetchone()
#     return fine_data


# NUEVO CODIGO SEGURO:


def get_fine_by_id(fine_id: int, user_id: int, db: db_dependency):
    if fine_id <= 0:
        raise HTTPException(400, "El id no es valido")
    fine_get = "SELECT * FROM fines WHERE id=%s AND user_id=%s"

    with db.cursor(dictonary=True) as cursor:
        cursor.execute(fine_get, (fine_id, user_id))
        fine_data = cursor.fetchone()

    if not fine_data:
        raise HTTPException(
            status_code=404, detail="No exite una multa asociada a este usuario"
        )

    return fine_data


def get_fine_ammount(fine_id: int, user_id: int) -> float:
    fine_data = get_fine_by_id(fine_id, user_id)
    return fine_data.amount


# =========================================================
# Modelos
# =========================================================


class LoginRequest(BaseModel):
    username: str
    password: str


class PayRequest(BaseModel):
    # 🔴 BOPLA: el cliente decide cuánto paga (se deja a propósito)
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
def login(data: LoginRequest, db: db_dependency):
    # 🔴 Sin rate limiting: fuerza bruta sin restricción
    user = get_user_by_username(data.username, db)
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
def get_fine(fine_id: int, db: db_dependency, authorization: str = Header(None)):
    current_user = get_current_user(authorization)
    fine = get_fine_by_id(fine_id, db)
    if not fine:
        raise HTTPException(status_code=404, detail="Multa no encontrada")

    # 🔴 No verifica fine["user_id"] == current_user["user_id"]
    return fine


# =========================================================
# 🔴 VULNERABILIDAD #3: BOPLA (mass assignment) + BOLA heredado
# ✅ FIX DE BUG (no de seguridad): ahora se guarda el charge id REAL
#    de Stripe (payment_intent.id) en vez de un UUID inventado.
# =========================================================


@app.post("/fines/{fine_id}/pay", status_code=200)
def pay_fine(
    fine_id: int,
    user_id,
    data: PayRequest,
    db: db_dependency,
    authorization: str = Header(None),
):
    current_user = get_current_user(authorization)
    fine = get_fine_by_id(fine_id, user_id, db)
    if not fine:
        raise HTTPException(status_code=404, detail="Multa no encontrada")

    ammount_to_pay = get_fine_ammount(fine_id, user_id)

    if ammount_to_pay != data.amount:
        raise HTTPException(status_code=403, detail="La cantidad a pagar no es valida")

    try:
        payment_intent = stripe.PaymentIntent.create(
            amount=(round(data.amount * 100)),
            currency="usd",
            payment_method="pm_card_visa",
            confirm=True,
            automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
            description=f"Pago de multa #{fine_id}",
            metadata={"fine_id": str(fine_id), "user_id": str(current_user["user_id"])},
        )
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=402,
            detail=f"Hubo un error en stripe: {e.user_message or str(e)} ",
        )

    # ✅ Antes acá se guardaba un f"ch_mock_{uuid.uuid4().hex[:16]}" inventado.
    #    Ahora se persiste el id real que devuelve Stripe.
    insert_invoice(
        fine_id,
        current_user["user_id"],
        data.amount,
        payment_intent.id,  # <-- antes: stripe_charge_id (UUID mock)
        payment_intent.status,
        db,
    )

    return {
        "message": "Pago procesado",
        "stripe_id": payment_intent.id,
        "status": payment_intent.status,
    }


@app.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: int, db: db_dependency, authorization: str = Header(None)):
    current_user = get_current_user(authorization)
    invoice = get_invoice_by_id(invoice_id, db)
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    # 🔴 BOLA otra vez: no valida invoice["user_id"] == current_user["user_id"]
    return invoice


@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    """
    Stripe te llama a ESTE endpoint cuando pasa algo (pago confirmado,
    fallido, disputa, etc). Prueba con:

        stripe listen --forward-to localhost:8000/webhooks/stripe
        stripe trigger payment_intent.succeeded

    La verificación de firma es OBLIGATORIA: sin ella, cualquiera podría
    hacer POST a esta URL fingiendo ser Stripe y marcar pagos como exitosos.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Firma de webhook inválida")

    if event["type"] == "payment_intent.succeeded":
        pi = event["data"]["object"]
        print(
            f"✅ Pago confirmado en Stripe: {pi['id']} — fine_id={pi['metadata'].get('fine_id')}"
        )
    elif event["type"] == "payment_intent.payment_failed":
        pi = event["data"]["object"]
        print(f"❌ Pago falló: {pi['id']}")

    return {"received": True}


@app.get("/")
def root():
    return {"status": "API de multas corriendo (VERSIÓN VULNERABLE)"}
