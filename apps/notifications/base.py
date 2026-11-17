from abc import ABC, abstractmethod


class BaseNotificationBackend(ABC):
    """Abstract base class for notification dispatch backends."""

    @abstractmethod
    def send_verification_otp(self, destination: str, code: str, purpose: str = "signup") -> bool:
        """Send verification OTP code to destination (email or phone)."""
        pass
