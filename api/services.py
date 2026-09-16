from datetime import datetime
from typing import Annotated

from fastapi import Depends, HTTPException
from mysql.connector.pooling import PooledMySQLConnection

from api.database import get_db

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


def get_invoice_by_id(invoice_id: int, user_id: int, db):
    query = "SELECT * FROM invoices WHERE id=%s AND user_id=%s"
    with db.cursor(dictionary=True) as cursor:
        cursor.execute(
            query,
            (
                invoice_id,
                user_id,
            ),
        )
        invoice_data = cursor.fetchone()

    if not invoice_data:
        raise HTTPException(status_code=404, detail="No se ha encontrado la factura")
    return invoice_data


# def mark_fine_as_paid(fine_id, db: db_dependency):
#     if fine_id <= 0:
#         raise HTTPException(400, "El id no es valido")
#     update_query = "UPDATE fines SET paid=TRUE WHERE id=%s"
#     with db.cursor(dictionary=True) as cursor:
#         cursor.execute(update_query, (fine_id,))
#         db.commit()


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

    db.start_transaction(isolation_level="SERIALIZABLE")
    with db.cursor(dictionary=True) as cursor:

        cursor.execute(
            "SELECT * FROM fines WHERE id=%s FOR UPDATE",
            (fine_id,),
        )
        fine = cursor.fetchone()
        if not fine:
            db.rollback()
            raise HTTPException(status_code=404, detail="Multa no encontrada")

        if fine["paid"]:
            db.rollback()
            raise HTTPException(status_code=409, detail="La multa ya está pagada")

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
        return {
            "message": "Pago procesado",
            "stripe_id": stripe_charge_id,
            "status": stripe_status,
        }


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
