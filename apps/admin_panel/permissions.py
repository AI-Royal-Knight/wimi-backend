from rest_framework import permissions


class IsPlatformAdmin(permissions.BasePermission):
    """
    Permission check strictly granting access to verified administrators.
    Allows users who have role == 'admin' or is_staff or is_superuser.
    """
    message = "Administrator privileges are strictly required to access this portal."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        return (
            getattr(user, "role", None) == "admin"
            or getattr(user, "is_staff", False)
            or getattr(user, "is_superuser", False)
        )

