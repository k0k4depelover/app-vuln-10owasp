import os
from errno import errorcode

import mysql.connector
from fastapi import HTTPException
from mysql.connector import pooling

# Se define un connection pool para evitar abrir una coneccion en cada peticion

connection_pool = mysql.connector.pooling.MySQLConnectionPool(
    pool_name="multas_pool",
    pool_size=5,
    host=MYSQL_HOST,
    port=MYSQL_PORT,
    user=os.getenv("MYSQL_USER"),
    password=os.getenv("MYSQL_PASSWORD"),
    database=os.getenv("MYSQL_DATABASE"),
)


def get_db():
    conn = None
    try:
        conn = connection_pool.get_connection()
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
