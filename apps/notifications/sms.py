import logging
from typing import List, Dict, Any
from .base import BaseNotificationBackend

logger = logging.getLogger(__name__)


class ConsoleSMSBackend(BaseNotificationBackend):
    """Console/Logger SMS dispatch backend for development."""

    def send_verification_otp(self, destination: str, code: str, purpose: str = "signup") -> bool:
        logger.info(
            "[SMS MOCK] To: %s | Purpose: %s | 4-Digit Code: %s",
            destination,
            purpose,
            code,
        )
        return True


class LocMemSMSBackend(BaseNotificationBackend):
    """In-memory SMS backend for testing assertions."""
    outbox: List[Dict[str, Any]] = []

    def send_verification_otp(self, destination: str, code: str, purpose: str = "signup") -> bool:
        self.outbox.append({
            "destination": destination,
            "code": code,
            "purpose": purpose,
        })
        return True

    @classmethod
    def clear(cls):
        cls.outbox.clear()
