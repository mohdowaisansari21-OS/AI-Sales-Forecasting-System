"""
Minimal email sender for OTP + password-reset emails.

If SMTP_HOST / SMTP_USER / SMTP_PASSWORD aren't set as environment
variables, emails are printed to the console instead of sent - so you
can build and test the whole flow before wiring up a real mail
provider (Gmail App Password, SendGrid, Mailgun, etc).

If SMTP IS configured but the send fails or hangs (wrong port, wrong
password, firewall silently dropping the connection), the send is
capped at a short timeout and falls back to printing the email to the
console - so a broken mail provider never blocks registration/login,
it just tells you clearly what went wrong.
"""
from dotenv import load_dotenv
import os
load_dotenv()
import smtplib
from email.mime.text import MIMEText

SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
SMTP_FROM = os.environ.get("SMTP_FROM")
SMTP_TIMEOUT_SECONDS = 10


def _print_fallback(to_email: str, subject: str, body: str, reason: str):
    print("=" * 60)
    print(f"[mailer] {reason} - printing email instead of sending it.")
    print(f"To:      {to_email}")
    print(f"Subject: {subject}")
    print("-" * 60)
    print(body)
    print("=" * 60)


def send_email(to_email: str, subject: str, body: str):
    if not (SMTP_HOST and SMTP_USER and SMTP_PASSWORD):
        _print_fallback(to_email, subject, body, "SMTP not configured")
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_email

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT_SECONDS) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, [to_email], msg.as_string())
    except Exception as exc:
        # Don't let a broken mail provider block registration/login - and
        # don't hang forever on a silently-dropped connection either.
        _print_fallback(to_email, subject, body, f"SMTP send failed ({exc})")
