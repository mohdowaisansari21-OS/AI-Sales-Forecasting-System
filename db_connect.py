import os

import mysql.connector

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def get_connection():
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST"),
        port=int(os.environ.get("DB_PORT", 3306)),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        database=os.environ.get("DB_NAME"),
        ssl_ca=os.environ.get("DB_SSL_CA"),
        ssl_verify_cert=True,
    )