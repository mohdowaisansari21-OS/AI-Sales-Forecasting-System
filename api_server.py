import os
from datetime import timedelta
from typing import List

import jwt
import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Header, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from secure import Secure

from auth import (
    authenticate,
    create_token,
    decode_token,
    create_pending_user,
    delete_unverified,
    verify_otp,
    resend_otp,
    get_user,
    get_user_by_email,
    is_valid_email,
    create_password_reset,
    reset_password_with_token,
)
from mailer import send_email


FORECAST_DAYS = 14
MODEL_PATH = "sales_model.pkl"
DATA_CSV_PATH = "sales_data.csv"
FRONTEND_BASE_URL = os.environ.get("FRONTEND_BASE_URL", "http://127.0.0.1:5500/frontend")

# Set ENVIRONMENT=production in Render's dashboard (or just leave it unset -
# "production" is the default, so /docs and /redoc are disabled unless you
# explicitly set ENVIRONMENT=development while working locally).
IS_PRODUCTION = os.environ.get("ENVIRONMENT", "production") == "production"

# Loaded once at startup. This is the model produced by train_model.py
# (trained on sales_data.csv via preprocess.py), not a live in-memory fit.
_model_bundle = None
if os.path.exists(MODEL_PATH):
    try:
        _model_bundle = joblib.load(MODEL_PATH)
    except Exception as exc:  # pragma: no cover - startup diagnostic only
        print(f"Warning: could not load {MODEL_PATH}: {exc}")


class SalesRow(BaseModel):
    date: str
    product: str | None = None
    region: str | None = None
    sales: float


class ForecastRequest(BaseModel):
    rows: List[SalesRow]


class LoginRequest(BaseModel):
    identifier: str  # username OR email
    password: str


class RegisterRequest(BaseModel):
    first_name: str
    last_name: str
    email: str
    username: str
    password: str


class VerifyOtpRequest(BaseModel):
    email: str
    otp: str


class ResendOtpRequest(BaseModel):
    email: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    email: str
    token: str
    new_password: str


app = FastAPI(
    title="AI Sales Forecasting API",
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
)

# --- Rate limiting (protects login/OTP/password-reset from brute force) ---
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- CORS: only your real frontend origin may call this API ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://ai-sales-forecasting-system-1.onrender.com",
        "http://127.0.0.1:5500",  # keep for local frontend testing; remove if not needed
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

# --- Security headers on every response ---
secure_headers = Secure.with_default_headers()


@app.middleware("http")
async def set_secure_headers(request: Request, call_next):
    response = await call_next(request)
    secure_headers.set_headers(response)
    return response


def get_current_user(authorization: str | None = Header(default=None)):
    """
    Reads 'Authorization: Bearer <token>', validates it, and returns the
    username. Used as a dependency on any route that should require login.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")

    token = authorization.split(" ", 1)[1]
    try:
        return decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session token.")


@app.post("/api/auth/login")
@limiter.limit("5/minute")
def login(request: Request, payload: LoginRequest):
    user = authenticate(payload.identifier, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect username/email or password.")
    if not user["is_verified"]:
        raise HTTPException(
            status_code=403,
            detail="Please verify your email before logging in. Check your inbox for the OTP.",
        )
    token = create_token(user["username"])
    return {"token": token, "username": user["username"]}


@app.post("/api/auth/register")
@limiter.limit("5/minute")
def register(request: Request, payload: RegisterRequest):
    first_name = payload.first_name.strip()
    last_name = payload.last_name.strip()
    email = payload.email.strip().lower()
    username = payload.username.strip()

    if not first_name or not last_name:
        raise HTTPException(status_code=400, detail="First and last name are required.")
    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters.")
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    existing_username = get_user(username)
    if existing_username and existing_username["is_verified"]:
        raise HTTPException(status_code=409, detail="That username is already taken.")

    existing_email = get_user_by_email(email)
    if existing_email and existing_email["is_verified"]:
        raise HTTPException(status_code=409, detail="An account with that email already exists.")

    # Clear out any abandoned, never-verified attempt using this username
    # or email so it doesn't block a fresh registration.
    delete_unverified(username=username, email=email)

    otp = create_pending_user(first_name, last_name, email, username, payload.password)
    send_email(
        email,
        "Your verification code",
        f"Hi {first_name},\n\n"
        f"Your AI Sales Forecasting verification code is: {otp}\n"
        f"It expires in 10 minutes.\n\n"
        f"If you didn't request this, you can ignore this email.",
    )
    return {"message": "Verification code sent to your email.", "email": email}


@app.post("/api/auth/verify-otp")
@limiter.limit("5/minute")
def verify_otp_route(request: Request, payload: VerifyOtpRequest):
    email = payload.email.strip().lower()
    if not verify_otp(email, payload.otp.strip()):
        raise HTTPException(status_code=400, detail="That code is invalid or has expired.")

    user = get_user_by_email(email)
    token = create_token(user["username"])
    return {"token": token, "username": user["username"]}


@app.post("/api/auth/resend-otp")
@limiter.limit("3/hour")
def resend_otp_route(request: Request, payload: ResendOtpRequest):
    email = payload.email.strip().lower()
    otp = resend_otp(email)
    if otp:
        send_email(
            email,
            "Your verification code",
            f"Your new verification code is: {otp}\nIt expires in 10 minutes.",
        )
    # Always the same response, whether or not the email exists/needs it -
    # avoids revealing which emails are registered.
    return {"message": "If that email needs verification, a new code has been sent."}


@app.post("/api/auth/forgot-password")
@limiter.limit("3/hour")
def forgot_password(request: Request, payload: ForgotPasswordRequest):
    email = payload.email.strip().lower()
    token = create_password_reset(email)
    if token:
        reset_link = f"{FRONTEND_BASE_URL}/reset-password.html?email={email}&token={token}"
        send_email(
            email,
            "Reset your password",
            f"We received a request to reset your password.\n\n"
            f"Reset it here (expires in 30 minutes):\n{reset_link}\n\n"
            f"If you didn't request this, you can ignore this email.",
        )
    # Same response either way - don't reveal whether the email is registered.
    return {"message": "If that email is registered, a reset link has been sent."}


@app.post("/api/auth/reset-password")
@limiter.limit("5/minute")
def reset_password(request: Request, payload: ResetPasswordRequest):
    email = payload.email.strip().lower()
    if len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
    if not reset_password_with_token(email, payload.token, payload.new_password):
        raise HTTPException(status_code=400, detail="That reset link is invalid or has expired.")
    return {"message": "Password updated. You can now log in."}


@app.get("/api/data")
@limiter.limit("30/minute")
def get_data(request: Request, user: str = Depends(get_current_user)):
    """
    Serves the full contents of sales_data.csv as JSON, so the frontend
    always reflects whatever data is on the server - not a hardcoded
    sample - without requiring a manual file upload.
    """
    if not os.path.exists(DATA_CSV_PATH):
        raise HTTPException(status_code=404, detail=f"{DATA_CSV_PATH} not found on server.")

    df = pd.read_csv(DATA_CSV_PATH)

    # Accept common column-name variants and normalize to what the
    # frontend expects: Date, Product, Region, Sales.
    rename_map = {}
    for col in df.columns:
        key = col.strip().lower()
        if key == "date":
            rename_map[col] = "Date"
        elif key in ("product", "category"):
            rename_map[col] = "Product"
        elif key == "region":
            rename_map[col] = "Region"
        elif key in ("sales", "revenue"):
            rename_map[col] = "Sales"
    df = df.rename(columns=rename_map)

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Sales"] = pd.to_numeric(df.get("Sales"), errors="coerce")
    df = df.dropna(subset=["Date", "Sales"]).sort_values("Date")

    if "Product" not in df.columns:
        df["Product"] = "General"
    if "Region" not in df.columns:
        df["Region"] = "All"

    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
    rows = df[["Date", "Product", "Region", "Sales"]].to_dict(orient="records")

    return {"rows": rows, "count": len(rows)}


@app.get("/api/health")
def health():
    return {"status": "ok", "trained_model_loaded": _model_bundle is not None}


@app.get("/api/forecast/trained")
@limiter.limit("20/minute")
def forecast_trained(request: Request, days: int = FORECAST_DAYS, user: str = Depends(get_current_user)):
    """
    Forecast using the model saved by train_model.py (trained on
    sales_data.csv), instead of fitting a new model on posted rows.
    Run train_model.py first if this 404s or errors.
    """
    if _model_bundle is None:
        raise HTTPException(
            status_code=404,
            detail="No trained model found. Run train_model.py first to create sales_model.pkl.",
        )

    model = _model_bundle["model"]
    last_day = _model_bundle["last_day"]
    last_date = pd.to_datetime(_model_bundle["last_date"])

    future_x = np.arange(last_day + 1, last_day + 1 + days).reshape(-1, 1)
    future_sales = np.maximum(0, model.predict(future_x))

    forecast_rows = []
    for offset, value in enumerate(future_sales, start=1):
        forecast_date = last_date + timedelta(days=offset)
        forecast_rows.append(
            {
                "date": forecast_date.strftime("%Y-%m-%d"),
                "sales": round(float(value), 2),
            }
        )

    first_forecast = float(future_sales[0])
    last_forecast = float(future_sales[-1])
    growth = 0.0 if first_forecast == 0 else ((last_forecast - first_forecast) / first_forecast) * 100

    return {
        "forecast_days": days,
        "forecast_change": round(growth, 2),
        "trained_on_rows": _model_bundle.get("trained_rows"),
        "trained_last_date": _model_bundle["last_date"],
        "forecast": forecast_rows,
        "source": "trained_model",
    }


@app.post("/api/forecast")
@limiter.limit("10/minute")
def forecast(request: Request, payload: ForecastRequest, user: str = Depends(get_current_user)):
    if len(payload.rows) < 2:
        raise HTTPException(status_code=400, detail="At least 2 sales records are required.")

    df = pd.DataFrame([row.dict() for row in payload.rows])
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["sales"] = pd.to_numeric(df["sales"], errors="coerce")
    df = df.dropna(subset=["date", "sales"]).sort_values("date").reset_index(drop=True)

    if len(df) < 2:
        raise HTTPException(status_code=400, detail="At least 2 valid sales records are required.")

    x = np.arange(len(df)).reshape(-1, 1)
    y = df["sales"].to_numpy()

    model = LinearRegression()
    model.fit(x, y)

    fitted = model.predict(x)
    fit_score = 1.0 if len(set(y)) == 1 else max(0.0, float(r2_score(y, fitted)))

    future_x = np.arange(len(df), len(df) + FORECAST_DAYS).reshape(-1, 1)
    future_sales = np.maximum(0, model.predict(future_x))
    last_date = df["date"].iloc[-1]

    forecast_rows = []
    for index, value in enumerate(future_sales, start=1):
        forecast_date = last_date + timedelta(days=index)
        forecast_rows.append(
            {
                "date": forecast_date.strftime("%Y-%m-%d"),
                "sales": round(float(value), 2),
            }
        )

    first_forecast = float(future_sales[0])
    last_forecast = float(future_sales[-1])
    growth = 0.0 if first_forecast == 0 else ((last_forecast - first_forecast) / first_forecast) * 100

    return {
        "forecast_days": FORECAST_DAYS,
        "forecast_change": round(growth, 2),
        "trend_fit": round(fit_score * 100, 2),
        "forecast": forecast_rows,
        "source": "python_backend",
    }
