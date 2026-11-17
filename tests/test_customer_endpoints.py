import pytest
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import User, MerchantStore
from apps.merchant.models import Product, Order, OrderItem
from apps.customer.models import CustomerAddress, CustomerFavorite, PromoBanner


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def customer_user(db):
    user = User.objects.create_user(
        email="customer.jane@email.com",
        phone="+50937000001",
        full_name="Jane Customer",
        password="Password123!",
    )
    user.is_active = True
    user.is_verified = True
    user.save()
    return user


@pytest.fixture
def merchant_with_store(db):
    owner = User.objects.create_user(
        email="merchant.boss@email.com",
        phone="+50937000002",
        full_name="Boss Merchant",
        role=User.ROLE_MERCHANT,
        password="Password123!",
    )
    owner.is_active = True
    owner.is_verified = True
    owner.save()

    store = MerchantStore.objects.create(
        owner=owner,
        name="Fresh Market Port-au-Prince",
        category=MerchantStore.CATEGORY_GROCERY,
        address="123 Rue de la République",
        is_verified=True,
        is_open=True,
        rating=4.9,
        reviews_count=120,
    )

    product1 = Product.objects.create(
        store=store,
        name="Fresh Mangoes",
        category="Fruits",
        sku="SKU-MANGO-01",
        price=3.99,
        discount_price=5.50,
        stock=50,
        sold_count=42,
        status=Product.STATUS_ACTIVE,
    )

    product2 = Product.objects.create(
        store=store,
        name="Avocados",
        category="Vegetables",
        sku="SKU-AVO-02",
        price=4.50,
        stock=30,
        sold_count=15,
        status=Product.STATUS_ACTIVE,
    )

    return {"owner": owner, "store": store, "products": [product1, product2]}


@pytest.mark.django_db
def test_customer_home_view(api_client, merchant_with_store):
    res = api_client.get("/api/v1/customer/home/")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["success"] is True
    assert "banners" in data["data"]
    assert len(data["data"]["banners"]) >= 1
    assert "categories" in data["data"]
    assert len(data["data"]["categories"]) >= 4
    assert "trending_products" in data["data"]
    assert len(data["data"]["trending_products"]) >= 2
    assert "top_stores" in data["data"]
    assert len(data["data"]["top_stores"]) >= 1


@pytest.mark.django_db
def test_customer_products_and_stores_search(api_client, merchant_with_store):
    # Test products list
    res = api_client.get("/api/v1/customer/products/?search=Mango")
    assert res.status_code == status.HTTP_200_OK
    assert len(res.json()["data"]) == 1
    assert res.json()["data"][0]["name"] == "Fresh Mangoes"

    # Test stores list
    res_stores = api_client.get("/api/v1/customer/stores/?search=Fresh")
    assert res_stores.status_code == status.HTTP_200_OK
    assert len(res_stores.json()["data"]) >= 1
    assert res_stores.json()["data"][0]["name"] == "Fresh Market Port-au-Prince"


@pytest.mark.django_db
def test_customer_addresses_crud(api_client, customer_user):
    api_client.force_authenticate(user=customer_user)

    # 1. Create first address (should automatically be default)
    res = api_client.post(
        "/api/v1/customer/addresses/",
        {
            "label": "Home",
            "street_address": "123 Rue de la République",
            "city": "Port-au-Prince",
            "details": "Apartment 4B",
        },
        format="json",
    )
    assert res.status_code == status.HTTP_201_CREATED
    addr1_id = res.json()["data"]["id"]
    assert res.json()["data"]["is_default"] is True

    # 2. Create second address (Office)
    res2 = api_client.post(
        "/api/v1/customer/addresses/",
        {
            "label": "Office",
            "street_address": "456 Avenue Jean-Jacques Dessalines",
            "city": "Port-au-Prince",
            "details": "3rd Floor",
            "is_default": False,
        },
        format="json",
    )
    assert res2.status_code == status.HTTP_201_CREATED
    addr2_id = res2.json()["data"]["id"]

    # 3. List addresses
    list_res = api_client.get("/api/v1/customer/addresses/")
    assert list_res.status_code == status.HTTP_200_OK
    assert len(list_res.json()["data"]) == 2

    # 4. Set second address as default
    set_def_res = api_client.post(f"/api/v1/customer/addresses/{addr2_id}/set-default/")
    assert set_def_res.status_code == status.HTTP_200_OK
    assert set_def_res.json()["data"]["is_default"] is True

    # Verify first is no longer default
    get_addr1 = api_client.get(f"/api/v1/customer/addresses/{addr1_id}/")
    assert get_addr1.json()["data"]["is_default"] is False

    # 5. Delete an address
    del_res = api_client.delete(f"/api/v1/customer/addresses/{addr1_id}/")
    assert del_res.status_code == status.HTTP_200_OK
    assert CustomerAddress.objects.filter(pk=addr1_id).exists() is False


@pytest.mark.django_db
def test_customer_orders_list(api_client, customer_user, merchant_with_store):
    store = merchant_with_store["store"]
    prod = merchant_with_store["products"][0]

    # Create order for customer
    order = Order.objects.create(
        store=store,
        order_number="#TB-2024-9001",
        customer=customer_user,
        customer_name=customer_user.full_name,
        customer_email=customer_user.email,
        customer_phone=customer_user.phone,
        delivery_address="123 Rue de la République",
        subtotal=10.00,
        delivery_fee=2.00,
        total_amount=12.00,
        status=Order.STATUS_DELIVERED,
    )
    OrderItem.objects.create(
        order=order,
        product=prod,
        product_name=prod.name,
        price=prod.price,
        quantity=2,
    )

    api_client.force_authenticate(user=customer_user)
    res = api_client.get("/api/v1/customer/orders/")
    assert res.status_code == status.HTTP_200_OK
    orders = res.json()["data"]
    assert len(orders) == 1
    assert orders[0]["order_number"] == "#TB-2024-9001"
    assert orders[0]["store_name"] == store.name
    assert orders[0]["items_count"] == 2
    assert orders[0]["display_status"] == "Delivered"


@pytest.mark.django_db
def test_customer_favorites_toggle(api_client, customer_user, merchant_with_store):
    api_client.force_authenticate(user=customer_user)
    prod = merchant_with_store["products"][0]
    store = merchant_with_store["store"]

    # Toggle product favorite (add)
    res = api_client.post("/api/v1/customer/favorites/", {"product_id": str(prod.id)}, format="json")
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["is_favorited"] is True

    # Toggle store favorite (add)
    res_s = api_client.post("/api/v1/customer/favorites/", {"store_id": str(store.id)}, format="json")
    assert res_s.status_code == status.HTTP_200_OK
    assert res_s.json()["is_favorited"] is True

    # Get favorites list
    get_fav = api_client.get("/api/v1/customer/favorites/")
    assert get_fav.status_code == status.HTTP_200_OK
    assert len(get_fav.json()["data"]["products"]) == 1
    assert len(get_fav.json()["data"]["stores"]) == 1
    assert get_fav.json()["data"]["total_count"] == 2

    # Toggle product favorite again (remove)
    res_toggle = api_client.post("/api/v1/customer/favorites/", {"product_id": str(prod.id)}, format="json")
    assert res_toggle.status_code == status.HTTP_200_OK
    assert res_toggle.json()["is_favorited"] is False


@pytest.mark.django_db
def test_customer_profile_summary(api_client, customer_user):
    api_client.force_authenticate(user=customer_user)
    res = api_client.get("/api/v1/customer/profile-summary/")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()["data"]
    assert "active_orders_count" in data
    assert "total_orders_count" in data
    assert "addresses_count" in data
    assert "favorites_count" in data

