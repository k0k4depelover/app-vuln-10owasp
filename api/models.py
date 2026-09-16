from pydantic import BaseModel

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
