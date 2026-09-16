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
from typing import Annotated

import jwt
import stripe
from auth import get_current_user
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from models import LoginRequest, PayRequest
from mysql.connector.pooling import PooledMySQLConnection

from services import (
    get_fine_by_id,
    get_invoice_by_id,
    get_user_by_username,
    insert_invoice,
)

load_dotenv()


from api.database import get_db

db_dependency = Annotated[PooledMySQLConnection, Depends(get_db)]


stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

app = FastAPI(title="Multas API (VULNERABLE)")


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


# CODIGO CORREGIDO
@app.get("/fines/{fine_id}")
def get_fine(fine_id: int, db: db_dependency, authorization: str = Header(None)):
    current_user = get_current_user(authorization)
    fine = get_fine_by_id(fine_id, current_user["user_id"], db)
    if not fine:
        raise HTTPException(status_code=404, detail="Multa no encontrada")
    return fine


# CODIGO CORREGIDO
@app.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: int, db: db_dependency, authorization: str = Header(None)):
    current_user = get_current_user(authorization)
    invoice = get_invoice_by_id(invoice_id, current_user["user_id"], db)
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    return invoice


# =========================================================
# 🔴 VULNERABILIDAD #3: BOPLA (mass assignment) + BOLA heredado
# ✅ FIX DE BUG (no de seguridad): ahora se guarda el charge id REAL
#    de Stripe (payment_intent.id) en vez de un UUID inventado.
# =========================================================


@app.post("/fines/{fine_id}/pay", status_code=200)
def pay_fine(
    fine_id: int,
    data: PayRequest,
    db: db_dependency,
    authorization: str = Header(None),
):
    current_user = get_current_user(authorization)
    fine = get_fine_by_id(fine_id, current_user["user_id"], db)
    if not fine:
        raise HTTPException(status_code=404, detail="Multa no encontrada")

    ammount_to_pay = get_fine_ammount(fine_id, current_user["user_id"])

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
        payment_intent.id,
        payment_intent.status,
        db,
    )

    return {
        "message": "Pago procesado",
        "stripe_id": payment_intent.id,
        "status": payment_intent.status,
    }


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
