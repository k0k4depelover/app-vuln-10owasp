import os
import time
from errno import errorcode

import mysql.connector
import mysql.connector.pooling
from fastapi import HTTPException
from mysql.connector import errorcode

# Se define un connection pool para evitar abrir una coneccion en cada peticion
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = os.getenv("MYSQL_PORT", 3306)
MAX_RETRIES = 10
RETRY_DELAY_SECONDS = 3


def create_pool_with_retries():
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            pool = mysql.connector.pooling.MySQLConnectionPool(
                pool_name="multas_pool",
                pool_size=5,
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=os.getenv("MYSQL_USER"),
                password=os.getenv("MYSQL_PASSWORD"),
                database=os.getenv("MYSQL_DATABASE"),
            )
            print(f"✅ Conectado a MySQL (intento {attempt}/{MAX_RETRIES})")
            return pool
        except mysql.connector.Error as err:
            last_error = err
            time.sleep(RETRY_DELAY_SECONDS)

    raise RuntimeError(
        f"No se pudo conectar a MySQL tras {MAX_RETRIES} intentos"
    ) from last_error


connection_pool = create_pool_with_retries()


def get_db():
    conn = None
    try:
        conn = connection_pool.get_connection()
        conn.autocommit = True
        yield conn
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            raise HTTPException(
                status_code=500, detail="Usuario o contraseña de DB incorrectos"
            )
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            raise HTTPException(status_code=500, detail="La base de datos no existe")
        else:
            raise HTTPException(status_code=500, detail="Error de base de datos")
    finally:
        if conn is not None:
            conn.close()
