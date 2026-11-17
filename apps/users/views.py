from rest_framework import generics, permissions, status, parsers
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse
from .models import MerchantStore
from .serializers import UserSerializer, UserProfileUpdateSerializer, MerchantStoreSerializer


class UserProfileView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete currently authenticated user's profile.
    Supports GET, PUT, PATCH and DELETE methods with JSON and multipart/form-data.
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return UserProfileUpdateSerializer
        return UserSerializer

    def get_object(self):
        return self.request.user

    @extend_schema(
        summary="Get Current User Profile",
        description="Returns details for currently authenticated user.",
        responses={200: UserSerializer},
    )
    def get(self, request, *args, **kwargs):
        serializer = UserSerializer(request.user, context={"request": request})
        return Response({"success": True, "data": serializer.data})

    @extend_schema(
        summary="Update Current User Profile",
        description="Update profile fields (full_name, phone, avatar).",
        request=UserProfileUpdateSerializer,
        responses={200: UserSerializer},
    )
    def patch(self, request, *args, **kwargs):
        user = self.get_object()
        serializer = UserProfileUpdateSerializer(
            user,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "success": True,
                "message": "Profile updated successfully.",
                "data": UserSerializer(user, context={"request": request}).data,
            },
            status=status.HTTP_200_OK,
        )

    def put(self, request, *args, **kwargs):
        return self.patch(request, *args, **kwargs)

    @extend_schema(
        summary="Delete Current User Profile",
        description="Permanently deletes the authenticated user account and all associated data.",
        responses={200: OpenApiResponse(description="Account permanently deleted")},
    )
    def delete(self, request, *args, **kwargs):
        user = self.get_object()
        user.delete()
        return Response(
            {
                "success": True,
                "message": "Account permanently deleted.",
            },
            status=status.HTTP_200_OK,
        )


class MerchantStoreView(generics.RetrieveUpdateAPIView):
    """
    Retrieve, create or update the merchant store belonging to authenticated user.
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]
    serializer_class = MerchantStoreSerializer

    def get_object(self):
        user = self.request.user
        store, _ = MerchantStore.objects.get_or_create(
            owner=user,
            defaults={
                "name": f"{user.full_name}'s Store",
                "category": MerchantStore.CATEGORY_GROCERY,
            },
        )
        return store

    @extend_schema(
        summary="Get Merchant Store",
        description="Returns details of the merchant store for the authenticated user.",
        responses={200: MerchantStoreSerializer},
    )
    def get(self, request, *args, **kwargs):
        store = self.get_object()
        serializer = MerchantStoreSerializer(store, context={"request": request})
        return Response({"success": True, "has_store": True, "data": serializer.data})

    @extend_schema(
        summary="Create or Update Merchant Store",
        description="Creates or updates the merchant store belonging to authenticated user.",
        request=MerchantStoreSerializer,
        responses={200: MerchantStoreSerializer},
    )
    def post(self, request, *args, **kwargs):
        user = request.user
        store = getattr(user, "merchant_store", None)
        if not store:
            serializer = MerchantStoreSerializer(
                data=request.data,
                context={"request": request},
            )
            serializer.is_valid(raise_exception=True)
            store = serializer.save(owner=user)
            return Response(
                {
                    "success": True,
                    "message": "Store created successfully.",
                    "data": serializer.data,
                },
                status=status.HTTP_201_CREATED,
            )
        return self.patch(request, *args, **kwargs)

    @extend_schema(
        summary="Update Merchant Store",
        description="Update merchant store attributes (name, description, address, category, phone, logo, banner, is_open, etc.).",
        request=MerchantStoreSerializer,
        responses={200: MerchantStoreSerializer},
    )
    def patch(self, request, *args, **kwargs):
        store = self.get_object()
        serializer = MerchantStoreSerializer(
            store,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "success": True,
                "message": "Store updated successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def put(self, request, *args, **kwargs):
        return self.patch(request, *args, **kwargs)
