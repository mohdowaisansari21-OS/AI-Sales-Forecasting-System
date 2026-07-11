import datetime
import hashlib
import os
import re
import secrets

import bcrypt
import jwt

from db_connect import get_connection

SECRET_KEY = os.environ.get("JWT_SECRET", "dev-only-secret-change-me")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 12
OTP_EXPIRE_MINUTES = 10
RESET_TOKEN_EXPIRE_MINUTES = 30

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------- passwords ----------

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email or ""))


# ---------- session tokens (JWT) ----------

def create_token(username: str) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": username,
        "iat": now,
        "exp": now + datetime.timedelta(hours=TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> str:
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    return payload["sub"]


# ---------- short-lived codes/tokens (OTP + password reset) ----------

def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ---------- user lookups ----------

def get_user(username: str):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()


def get_user_by_email(email: str):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()


def get_user_by_identifier(identifier: str):
    """identifier can be a username OR an email - login accepts either."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT * FROM users WHERE username = %s OR email = %s",
            (identifier, identifier),
        )
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()


# ---------- registration + OTP verification ----------

def delete_unverified(username: str = None, email: str = None):
    """
    Removes any UNVERIFIED account matching this username or email.
    Used before a fresh registration attempt so an abandoned signup
    (created a pending account, never entered the OTP) doesn't
    permanently block that username/email from ever registering again.
    Verified accounts are never touched by this.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if email:
            cursor.execute("DELETE FROM users WHERE email = %s AND is_verified = FALSE", (email,))
        if username:
            cursor.execute("DELETE FROM users WHERE username = %s AND is_verified = FALSE", (username,))
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def create_pending_user(first_name, last_name, email, username, password) -> str:
    """Creates an unverified account and returns the OTP to email to the user."""
    otp = generate_otp()
    expires = datetime.datetime.utcnow() + datetime.timedelta(minutes=OTP_EXPIRE_MINUTES)

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO users
                (first_name, last_name, email, username, password_hash,
                 is_verified, otp_code, otp_expires_at)
            VALUES (%s, %s, %s, %s, %s, FALSE, %s, %s)
            """,
            (first_name, last_name, email, username, hash_password(password), otp, expires),
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    return otp


def create_verified_user(first_name, last_name, email, username, password):
    """Used only by setup_users_table.py to bootstrap an admin account with no OTP step."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO users (first_name, last_name, email, username, password_hash, is_verified)
            VALUES (%s, %s, %s, %s, %s, TRUE)
            """,
            (first_name, last_name, email, username, hash_password(password)),
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def verify_otp(email: str, otp: str) -> bool:
    user = get_user_by_email(email)
    if not user or not user.get("otp_code"):
        return False
    if user["otp_code"] != otp:
        return False
    if user["otp_expires_at"] and user["otp_expires_at"] < datetime.datetime.utcnow():
        return False

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE users SET is_verified = TRUE, otp_code = NULL, otp_expires_at = NULL WHERE email = %s",
            (email,),
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    return True


def resend_otp(email: str):
    """Generates a fresh OTP for an unverified account. Returns the OTP, or None if not applicable."""
    user = get_user_by_email(email)
    if not user or user["is_verified"]:
        return None

    otp = generate_otp()
    expires = datetime.datetime.utcnow() + datetime.timedelta(minutes=OTP_EXPIRE_MINUTES)
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE users SET otp_code = %s, otp_expires_at = %s WHERE email = %s",
            (otp, expires, email),
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    return otp


def authenticate(identifier: str, password: str):
    """Returns the user dict on success, or None. Does NOT check is_verified - caller decides."""
    user = get_user_by_identifier(identifier)
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user


# ---------- forgot password ----------

def create_password_reset(email: str):
    """Returns a plaintext reset token if the email exists, else None. Only the token's
    hash is stored in the DB - the plaintext token only ever exists in the emailed link."""
    user = get_user_by_email(email)
    if not user:
        return None

    token = secrets.token_urlsafe(32)
    expires = datetime.datetime.utcnow() + datetime.timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE users SET reset_token_hash = %s, reset_token_expires = %s WHERE email = %s",
            (hash_token(token), expires, email),
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    return token


def reset_password_with_token(email: str, token: str, new_password: str) -> bool:
    user = get_user_by_email(email)
    if not user or not user.get("reset_token_hash"):
        return False
    if user["reset_token_hash"] != hash_token(token):
        return False
    if user["reset_token_expires"] and user["reset_token_expires"] < datetime.datetime.utcnow():
        return False

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE users
            SET password_hash = %s, reset_token_hash = NULL, reset_token_expires = NULL
            WHERE email = %s
            """,
            (hash_password(new_password), email),
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    return True
