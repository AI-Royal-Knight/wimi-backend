import re
import secrets
from typing import Optional


def normalize_email(email: Optional[str]) -> str:
    """Normalize and lowercase email address."""
    if not email:
        return ""
    email = email.strip()
    try:
        email_name, domain_part = email.rsplit("@", 1)
        return f"{email_name.lower()}@{domain_part.lower()}"
    except ValueError:
        return email.lower()


def normalize_phone(phone: Optional[str]) -> str:
    """
    Normalize phone number.
    Preserves leading '+' if present and removes all whitespace, dashes, and parentheses.
    """
    if not phone:
        return ""
    phone = phone.strip()
    has_plus = phone.startswith("+")
    digits_only = re.sub(r"\D", "", phone)
    return f"+{digits_only}" if has_plus else digits_only


def generate_otp_code(digits: int = 4) -> str:
    """
    Generate a cryptographically secure numeric OTP code.
    Defaults to 4 digits as required by the frontend OtpVerifyPage.
    """
    # Range for 4 digits: 1000 to 9999
    lower_bound = 10 ** (digits - 1)
    upper_bound = (10 ** digits) - 1
    code = secrets.randbelow(upper_bound - lower_bound + 1) + lower_bound
    return str(code)


def generate_secure_token(nbytes: int = 32) -> str:
    """Generate a high-entropy URL-safe cryptographic token."""
    return secrets.token_urlsafe(nbytes)
