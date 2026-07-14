"""
Email sender for OTP + password-reset emails, using Brevo's HTTP API
instead of raw SMTP.

Why: Render's free tier blocks outbound traffic on SMTP ports (25, 465,
587) to prevent spam abuse, so smtplib connections fail with
"Network is unreachable" regardless of correct credentials. Brevo's API
sends email over regular HTTPS (port 443), which isn't blocked, so this
works on Render's free tier (or any host, or if you migrate hosts later).

If BREVO_API_KEY isn't set as an environment variable, emails are
printed to the console instead of sent - so you can build and test the
whole flow before wiring up a real Brevo account.

If the API call fails (bad key, sender not verified, quota hit, etc.),
the send is capped at a short timeout and falls back to printing the
email to the console - so a broken mail provider never blocks
registration/login, it just tells you clearly what went wrong.
"""

from dotenv import load_dotenv
import os

load_dotenv()

import requests

BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
SMTP_FROM = os.environ.get("SMTP_FROM")  # reused as the verified "from" address
BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"
BREVO_TIMEOUT_SECONDS = 10


def _print_fallback(to_email: str, subject: str, body: str, reason: str):
    print("=" * 60)
    print(f"[mailer] {reason} - printing email instead of sending it.")
    print(f"To: {to_email}")
    print(f"Subject: {subject}")
    print("-" * 60)
    print(body)
    print("=" * 60)


def send_email(to_email: str, subject: str, body: str):
    if not (BREVO_API_KEY and SMTP_FROM):
        _print_fallback(to_email, subject, body, "Brevo not configured")
        return

    payload = {
        "sender": {"email": SMTP_FROM},
        "to": [{"email": to_email}],
        "subject": subject,
        "textContent": body,
    }
    headers = {
        "api-key": BREVO_API_KEY,
        "Content-Type": "application/json",
        "accept": "application/json",
    }

    try:
        response = requests.post(
            BREVO_API_URL,
            json=payload,
            headers=headers,
            timeout=BREVO_TIMEOUT_SECONDS,
        )
        if not response.ok:
            # Surface Brevo's error detail (e.g. unverified sender, bad key,
            # quota exceeded) instead of a generic failure.
            raise RuntimeError(f"{response.status_code}: {response.text}")
    except Exception as exc:
        # Don't let a broken mail provider block registration/login - and
        # don't hang forever on a slow/unreachable API either.
        _print_fallback(to_email, subject, body, f"Brevo send failed ({exc})")
