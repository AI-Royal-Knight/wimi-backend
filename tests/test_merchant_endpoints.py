from decimal import Decimal
import pytest
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import User, MerchantStore
from apps.merchant.models import Product, Order, OrderItem, Transaction, PayoutRequest


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def merchant_user(db):
    user = User.objects.create_user(
        email="test.seller@example.com",
        phone="+242060000001",
        password="Password123!",
        full_name="Test Seller",
        role=User.ROLE_MERCHANT,
    )
    user.mark_verified()
    store = MerchantStore.objects.create(
        owner=user,
        name="Test Seller Market",
        category="Grocery",
        address="Brazzaville, Downtown",
        phone="+242060000001",
        bank_name="Chase Bank",
        account_number="4532",
        account_holder="Test Seller",
        routing_number="021000021",
    )
    return user


@pytest.fixture
def customer_user(db):
    user = User.objects.create_user(
        email="test.customer@example.com",
        phone="+242060000002",
        password="Password123!",
        full_name="Test Customer",
        role=User.ROLE_CUSTOMER,
    )
    user.mark_verified()
    return user


@pytest.fixture
def sample_product(merchant_user):
    return Product.objects.create(
        store=merchant_user.merchant_store,
        name="Organic Tomatoes",
        category="Vegetables",
        sku="TEST-TOM-01",
        price=Decimal("5.00"),
        stock=50,
        min_stock=10,
        max_stock=100,
        status=Product.STATUS_ACTIVE,
    )


@pytest.fixture
def sample_order(merchant_user, sample_product):
    order = Order.objects.create(
        store=merchant_user.merchant_store,
        order_number="#ORD-TEST-001",
        customer_name="Alice Smith",
        customer_email="alice@example.com",
        customer_phone="+1234567890",
        delivery_address="123 Test St",
        subtotal=Decimal("20.00"),
        delivery_fee=Decimal("5.00"),
        total_amount=Decimal("25.00"),
        status=Order.STATUS_NEW,
    )
    OrderItem.objects.create(
        order=order,
        product=sample_product,
        product_name=sample_product.name,
        price=Decimal("5.00"),
        quantity=4,
    )
    return order


@pytest.mark.django_db
class TestMerchantEndpoints:
    def test_unauthenticated_request_blocked(self, api_client):
        res = api_client.get("/api/v1/merchant/dashboard/")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED

    def test_customer_access_forbidden(self, api_client, customer_user):
        api_client.force_authenticate(user=customer_user)
        res = api_client.get("/api/v1/merchant/dashboard/")
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_merchant_dashboard(self, api_client, merchant_user, sample_order):
        api_client.force_authenticate(user=merchant_user)
        res = api_client.get("/api/v1/merchant/dashboard/")
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert data["success"] is True
        assert data["data"]["store_name"] == "Test Seller Market"
        assert len(data["data"]["recent_orders"]) >= 1

    def test_merchant_orders_filtering_and_acceptance(self, api_client, merchant_user, sample_order):
        api_client.force_authenticate(user=merchant_user)
        res = api_client.get("/api/v1/merchant/orders/?tab=new")
        assert res.status_code == status.HTTP_200_OK
        assert res.json()["count"] == 1

        # Accept order
        res_accept = api_client.post(f"/api/v1/merchant/orders/{sample_order.id}/accept/")
        assert res_accept.status_code == status.HTTP_200_OK
        assert res_accept.json()["data"]["status"] == Order.STATUS_PREPARING

        # Filter active
        res_active = api_client.get("/api/v1/merchant/orders/?tab=active")
        assert res_active.status_code == status.HTTP_200_OK
        assert res_active.json()["count"] == 1

    def test_merchant_product_crud_and_stock_adjust(self, api_client, merchant_user, sample_product):
        api_client.force_authenticate(user=merchant_user)

        # Create product
        res = api_client.post("/api/v1/merchant/products/", {
            "name": "Fresh Milk",
            "category": "Dairy",
            "sku": "TEST-MILK-02",
            "price": "4.50",
            "stock": 20,
            "min_stock": 5,
            "max_stock": 50,
            "status": "Active",
        })
        assert res.status_code == status.HTTP_201_CREATED
        prod_id = res.json()["data"]["id"]

        # Stock adjust (+10)
        res_stock = api_client.post(f"/api/v1/merchant/products/{prod_id}/stock/", {
            "action": "add",
            "quantity": 10,
        })
        assert res_stock.status_code == status.HTTP_200_OK
        assert res_stock.json()["data"]["stock"] == 30

        # Delete product
        res_del = api_client.delete(f"/api/v1/merchant/products/{prod_id}/")
        assert res_del.status_code == status.HTTP_200_OK

    def test_merchant_inventory_summary(self, api_client, merchant_user, sample_product):
        api_client.force_authenticate(user=merchant_user)
        res = api_client.get("/api/v1/merchant/inventory/")
        assert res.status_code == status.HTTP_200_OK
        summary = res.json()["summary"]
        assert summary["total_products"] == 1

    def test_merchant_earnings_and_payout(self, api_client, merchant_user):
        api_client.force_authenticate(user=merchant_user)

        # Add initial earning transaction
        Transaction.objects.create(
            store=merchant_user.merchant_store,
            transaction_id="TX-TEST-EARN",
            type=Transaction.TYPE_EARNING,
            description="Test sale settlement",
            amount=Decimal("500.00"),
            status=Transaction.STATUS_COMPLETED,
        )

        res = api_client.get("/api/v1/merchant/earnings/")
        assert res.status_code == status.HTTP_200_OK
        assert res.json()["data"]["available_balance"] == 500.0

        # Request payout
        res_payout = api_client.post("/api/v1/merchant/payouts/", {
            "amount": "200.00",
            "method": "Bank Transfer",
            "bank_name": "Chase Bank",
            "account_number": "4532",
            "account_holder": "Test Seller",
        })
        assert res_payout.status_code == status.HTTP_201_CREATED
        assert res_payout.json()["data"]["status"] == PayoutRequest.STATUS_PENDING

