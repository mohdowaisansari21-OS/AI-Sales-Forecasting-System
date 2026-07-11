"""
Creates the `users` table with the full signup schema (first name, last
name, email, OTP verification, password reset support), and optionally
creates a first admin account that skips the OTP step so you always
have a way to log in.

    python setup_users_table.py

If you already have an old-style `users` table (just username/password),
run reset_users_table.py first to drop it, then run this.
"""

from db_connect import get_connection
from auth import create_verified_user, get_user, get_user_by_email, is_valid_email


def create_users_table():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            first_name VARCHAR(100) NOT NULL,
            last_name VARCHAR(100) NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            username VARCHAR(100) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            is_verified BOOLEAN NOT NULL DEFAULT FALSE,
            otp_code VARCHAR(10) NULL,
            otp_expires_at DATETIME NULL,
            reset_token_hash VARCHAR(255) NULL,
            reset_token_expires DATETIME NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    cursor.close()
    conn.close()
    print("`users` table is ready (with first name / last name / email / OTP / reset columns).")


def create_first_admin():
    print("\nCreate a first account that's already verified (no OTP needed) so you can log in immediately.")
    first_name = input("First name: ").strip()
    last_name = input("Last name: ").strip()
    email = input("Email: ").strip()
    username = input("Username: ").strip()

    if not first_name or not last_name:
        print("First and last name are required.")
        return
    if not is_valid_email(email):
        print("That doesn't look like a valid email.")
        return
    if len(username) < 3:
        print("Username must be at least 3 characters.")
        return
    if get_user(username):
        print(f"Username '{username}' already exists - skipping.")
        return
    if get_user_by_email(email):
        print(f"Email '{email}' is already registered - skipping.")
        return

    import getpass
    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords did not match. Run this script again to retry.")
        return
    if len(password) < 6:
        print("Password should be at least 6 characters.")
        return

    create_verified_user(first_name, last_name, email, username, password)
    print(f"Account '{username}' created and verified. You can log in with it now.")


if __name__ == "__main__":
    create_users_table()
    answer = input("\nCreate a first (pre-verified) account now? [y/N]: ").strip().lower()
    if answer == "y":
        create_first_admin()
    else:
        print("Skipped. Run this script again anytime to add a pre-verified account.")
