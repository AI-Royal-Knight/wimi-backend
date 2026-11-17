from rest_framework.permissions import BasePermission
from apps.users.models import User


class IsMerchantUser(BasePermission):
    """
    Allows access only to authenticated users with 'merchant' or 'admin' role
    who have an associated MerchantStore.
    """
    message = "You must be an authenticated merchant with an active store to access this resource."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False

        if request.user.role not in [User.ROLE_MERCHANT, User.ROLE_ADMIN]:
            return False

        return hasattr(request.user, "merchant_store") and request.user.merchant_store is not None

