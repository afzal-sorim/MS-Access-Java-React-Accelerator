import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

# SMTP configuration
SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER)

def send_reset_email(email: str, token: str):
    """Send a password reset email using standard smtplib."""
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASSWORD]):
        print(f"WARNING: SMTP not configured. Password reset token for {email}: {token}")
        return

    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:5173")
    reset_url = f"{frontend_url}/reset-password?token={token}"

    message = MIMEMultipart("alternative")
    message["Subject"] = "Reset Your Password - Access2Java"
    message["From"] = SMTP_FROM
    message["To"] = email

    text = f"Hi,\n\nYou requested to reset your password. Click the link below to set a new password:\n\n{reset_url}\n\nIf you did not request this, please ignore this email."
    html = f"""
    <html>
      <body>
        <p>Hi,</p>
        <p>You requested to reset your password. Click the link below to set a new password:</p>
        <p><a href="{reset_url}">Reset Password</a></p>
        <p>If you did not request this, please ignore this email.</p>
      </body>
    </html>
    """

    message.attach(MIMEText(text, "plain"))
    message.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            if SMTP_PORT == 587:
                server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, email, message.as_string())
        print(f"Successfully sent reset email to {email}")
    except Exception as e:
        print(f"Failed to send reset email to {email}: {e}")
