import os

import mysql.connector
from mysql.connector import pooling

# Optional: if python-dotenv is installed, load a .env file automatically.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# Created once when this module is first imported, instead of opening a
# brand-new SSL connection on every single request. get_connection() then
# just borrows an already-open connection from this pool.
_pool = mysql.connector.pooling.MySQLConnectionPool(
    pool_name="sales_pool",
    pool_size=5,
    host=os.environ.get("DB_HOST"),
    port=int(os.environ.get("DB_PORT", 3306)),
    user=os.environ.get("DB_USER"),
    password=os.environ.get("DB_PASSWORD"),
    database=os.environ.get("DB_NAME"),
    ssl_ca=os.environ.get("DB_SSL_CA"),
    ssl_verify_cert=True,
)


def get_connection():
    return _pool.get_connection()