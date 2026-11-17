from django.urls import path
from .views import (
    CustomerAddressDetailView,
    CustomerAddressListCreateView,
    CustomerAddressSetDefaultView,
    CustomerFavoriteDetailDeleteView,
    CustomerFavoritesView,
    CustomerHomeView,
    CustomerOrderChatView,
    CustomerOrderDetailView,
    CustomerOrderRateView,
    CustomerOrdersView,
    CustomerProductDetailView,
    CustomerProductsListView,
    CustomerProfileSummaryView,
    CustomerStoreDetailView,
    CustomerStoresListView,
)

app_name = "customer"

urlpatterns = [
    # Marketplace Home & Discovery
    path("home/", CustomerHomeView.as_view(), name="home"),
    path("products/", CustomerProductsListView.as_view(), name="products-list"),
    path("products/<uuid:pk>/", CustomerProductDetailView.as_view(), name="product-detail"),
    path("stores/", CustomerStoresListView.as_view(), name="stores-list"),
    path("stores/<uuid:pk>/", CustomerStoreDetailView.as_view(), name="store-detail"),

    # Customer Orders
    path("orders/", CustomerOrdersView.as_view(), name="orders-list"),
    path("orders/chat/", CustomerOrderChatView.as_view(), name="order-chat-active"),
    path("orders/<str:order_lookup>/", CustomerOrderDetailView.as_view(), name="order-detail"),
    path("orders/<str:order_lookup>/rate/", CustomerOrderRateView.as_view(), name="order-rate"),
    path("orders/<str:order_lookup>/chat/", CustomerOrderChatView.as_view(), name="order-chat"),

    # Saved Addresses
    path("addresses/", CustomerAddressListCreateView.as_view(), name="addresses-list-create"),
    path("addresses/<uuid:pk>/", CustomerAddressDetailView.as_view(), name="address-detail"),
    path("addresses/<uuid:pk>/set-default/", CustomerAddressSetDefaultView.as_view(), name="address-set-default"),

    # Favorites & Wishlist
    path("favorites/", CustomerFavoritesView.as_view(), name="favorites"),
    path("favorites/<uuid:pk>/", CustomerFavoriteDetailDeleteView.as_view(), name="favorite-detail-delete"),

    # Customer Profile Summary
    path("profile-summary/", CustomerProfileSummaryView.as_view(), name="profile-summary"),
]

