import uuid
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from apps.customer.models import CustomerAddress, CustomerFavorite
from apps.merchant.models import MerchantStore, Order, Product
from apps.users.models import RiderProfile

User = get_user_model()


class CustomerApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="customer@example.com",
            password="SecurePassword123!",
            full_name="Jean Customer",
            phone="+50937112233",
            role=User.ROLE_CUSTOMER,
        )
        self.client.force_authenticate(user=self.user)

        self.merchant_user = User.objects.create_user(
            email="merchant@example.com",
            password="SecurePassword123!",
            full_name="Store Owner",
            role=User.ROLE_MERCHANT,
        )
        self.store = MerchantStore.objects.create(
            owner=self.merchant_user,
            name="TiBoutik Supermarché",
            category="Grocery",
            address="12 Rue Panaméricaine, Pétion-Ville",
            is_open=True,
        )
        self.product = Product.objects.create(
            store=self.store,
            name="Pain Créole",
            category="Bakery",
            price=Decimal("2.50"),
            stock=100,
        )

        self.rider_user = User.objects.create_user(
            email="rider@example.com",
            password="SecurePassword123!",
            full_name="Marc Antoine",
            phone="+50937998877",
            role=User.ROLE_RIDER,
        )
        self.rider = RiderProfile.objects.create(
            user=self.rider_user,
            vehicle_type="Motorcycle",
            number_plate="HT-4432",
            status=RiderProfile.STATUS_ACTIVE,
        )

    def test_customer_home(self):
        res = self.client.get("/api/v1/customer/home/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["success"])
        self.assertIn("categories", res.data["data"])
        self.assertIn("top_stores", res.data["data"])

    def test_order_creation_and_retrieval_and_rating(self):
        order_payload = {
            "store_id": str(self.store.id),
            "delivery_address": "45 Rue Capois, Port-au-Prince",
            "payment_method": "Cash on Delivery",
            "subtotal": "5.00",
            "delivery_fee": "2.00",
            "discount": "0.00",
            "total_amount": "7.00",
            "items": [
                {
                    "product_id": str(self.product.id),
                    "product_name": "Pain Créole",
                    "quantity": 2,
                    "price": "2.50",
                }
            ],
        }

        # 1. Create Order
        res = self.client.post("/api/v1/customer/orders/", data=order_payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data["success"])
        order_data = res.data["data"]
        order_id = order_data["id"]
        order_number = order_data["order_number"]
        self.assertEqual(order_data["rider_name"], "Marc Antoine")
        self.assertIsNotNone(order_data["otp_code"])

        # 2. Retrieve Order by UUID
        res_by_uuid = self.client.get(f"/api/v1/customer/orders/{order_id}/")
        self.assertEqual(res_by_uuid.status_code, status.HTTP_200_OK)
        self.assertEqual(res_by_uuid.data["data"]["id"], order_id)

        # 3. Retrieve Order by Order Number
        res_by_num = self.client.get(f"/api/v1/customer/orders/{order_number.replace('#', '')}/")
        self.assertEqual(res_by_num.status_code, status.HTTP_200_OK)
        self.assertEqual(res_by_num.data["data"]["id"], order_id)

        # 4. Rate Order
        rate_res = self.client.post(
            f"/api/v1/customer/orders/{order_id}/rate/",
            data={
                "store_rating": 5,
                "store_comment": "Excellent packaging!",
                "rider_rating": 5,
                "rider_comment": "Super fast delivery",
            },
            format="json",
        )
        self.assertEqual(rate_res.status_code, status.HTTP_200_OK)
        self.assertEqual(rate_res.data["data"]["status"], Order.STATUS_DELIVERED)

    def test_order_creation_with_string_product_id(self):
        order_payload = {
            "items": [
                {
                    "product_id": "1",
                    "product_name": "Fresh Organic Mangoes",
                    "quantity": 3,
                    "price": "3.99",
                    "image_url": "https://example.com/mango.jpg",
                }
            ],
            "delivery_address": "45 Rue Capois, Port-au-Prince",
            "payment_method": "Cash on Delivery",
            "subtotal": "11.97",
            "delivery_fee": "0.00",
            "discount": "2.00",
            "total_amount": "9.97",
        }
        res = self.client.post("/api/v1/customer/orders/", data=order_payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data["success"])
        self.assertEqual(res.data["data"]["items"][0]["product_name"], "Fresh Organic Mangoes")
        self.assertEqual(res.data["data"]["items_count"], 3)

    def test_customer_addresses_and_favorites(self):
        # Add Address
        addr_res = self.client.post(
            "/api/v1/customer/addresses/",
            data={
                "label": "Office",
                "street_address": "88 Blvd Toussaint Louverture",
                "city": "Port-au-Prince",
                "details": "Floor 3, Room 302",
                "is_default": True,
            },
            format="json",
        )
        self.assertEqual(addr_res.status_code, status.HTTP_201_CREATED)
        addr_id = addr_res.data["data"]["id"]

        # List Addresses
        list_res = self.client.get("/api/v1/customer/addresses/")
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_res.data["data"]), 1)

        # Toggle Favorite
        fav_res = self.client.post(
            "/api/v1/customer/favorites/",
            data={"product_id": str(self.product.id)},
            format="json",
        )
        self.assertEqual(fav_res.status_code, status.HTTP_200_OK)
        self.assertTrue(fav_res.data["is_favorited"])

        # Check Favorites list
        fav_list = self.client.get("/api/v1/customer/favorites/")
        self.assertEqual(fav_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(fav_list.data["data"]["products"]), 1)

    def test_customer_favorites_full_lifecycle_and_delete(self):
        # 1. Favorite product
        prod_res = self.client.post(
            "/api/v1/customer/favorites/",
            data={"product_id": str(self.product.id)},
            format="json",
        )
        self.assertEqual(prod_res.status_code, status.HTTP_200_OK)
        self.assertTrue(prod_res.data["is_favorited"])

        # 2. Favorite store
        store_res = self.client.post(
            "/api/v1/customer/favorites/",
            data={"store_id": str(self.store.id)},
            format="json",
        )
        self.assertEqual(store_res.status_code, status.HTTP_200_OK)
        self.assertTrue(store_res.data["is_favorited"])

        # 3. Retrieve favorites
        list_res = self.client.get("/api/v1/customer/favorites/")
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        self.assertEqual(list_res.data["data"]["total_count"], 2)
        self.assertEqual(len(list_res.data["data"]["products"]), 1)
        self.assertEqual(len(list_res.data["data"]["stores"]), 1)
        
        prod_data = list_res.data["data"]["products"][0]
        store_data = list_res.data["data"]["stores"][0]
        self.assertEqual(prod_data["name"], "Pain Créole")
        self.assertEqual(store_data["name"], "TiBoutik Supermarché")
        store_fav_id = store_data["favorite_id"]

        # 4. Check profile summary reflects 2 favorites
        summary_res = self.client.get("/api/v1/customer/profile-summary/")
        self.assertEqual(summary_res.status_code, status.HTTP_200_OK)
        self.assertEqual(summary_res.data["data"]["favorites_count"], 2)

        # 5. Delete product favorite via DELETE endpoint with product_id
        del_prod = self.client.delete(
            "/api/v1/customer/favorites/",
            data={"product_id": str(self.product.id)},
            format="json",
        )
        self.assertEqual(del_prod.status_code, status.HTTP_200_OK)
        self.assertFalse(del_prod.data["is_favorited"])

        # 6. Delete store favorite via detail DELETE endpoint with favorite_id
        del_store = self.client.delete(f"/api/v1/customer/favorites/{store_fav_id}/")
        self.assertEqual(del_store.status_code, status.HTTP_200_OK)
        self.assertFalse(del_store.data["is_favorited"])

        # 7. Final check - favorites list is now empty
        empty_list = self.client.get("/api/v1/customer/favorites/")
        self.assertEqual(empty_list.data["data"]["total_count"], 0)
        self.assertEqual(len(empty_list.data["data"]["products"]), 0)
        self.assertEqual(len(empty_list.data["data"]["stores"]), 0)

    def test_customer_address_full_crud_and_default_toggle(self):
        # 1. First address automatically becomes default
        res1 = self.client.post(
            "/api/v1/customer/addresses/",
            data={
                "label": "Home",
                "street_address": "123 Rue de la République",
                "city": "Port-au-Prince",
                "details": "Apt 4B",
                "is_default": False,
            },
            format="json",
        )
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        addr1_id = res1.data["data"]["id"]
        self.assertTrue(res1.data["data"]["is_default"])

        # 2. Second address created non-default
        res2 = self.client.post(
            "/api/v1/customer/addresses/",
            data={
                "label": "Work",
                "street_address": "45 Avenue John Brown",
                "city": "Port-au-Prince",
                "details": "Suite 200",
                "is_default": False,
            },
            format="json",
        )
        self.assertEqual(res2.status_code, status.HTTP_201_CREATED)
        addr2_id = res2.data["data"]["id"]
        self.assertFalse(res2.data["data"]["is_default"])

        # 3. Update second address with is_default=True via PATCH
        patch_res = self.client.patch(
            f"/api/v1/customer/addresses/{addr2_id}/",
            data={"label": "Headquarters", "is_default": True},
            format="json",
        )
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res.data["data"]["label"], "Headquarters")
        self.assertTrue(patch_res.data["data"]["is_default"])

        # Verify address 1 is no longer default
        get_addr1 = self.client.get(f"/api/v1/customer/addresses/{addr1_id}/")
        self.assertFalse(get_addr1.data["data"]["is_default"])

        # 4. Set address 1 as default using the explicit set-default endpoint
        set_def_res = self.client.post(f"/api/v1/customer/addresses/{addr1_id}/set-default/")
        self.assertEqual(set_def_res.status_code, status.HTTP_200_OK)
        self.assertTrue(set_def_res.data["data"]["is_default"])

        # Verify address 2 is no longer default
        get_addr2 = self.client.get(f"/api/v1/customer/addresses/{addr2_id}/")
        self.assertFalse(get_addr2.data["data"]["is_default"])

        # 5. Delete address 1 (current default), address 2 should become default
        del_res = self.client.delete(f"/api/v1/customer/addresses/{addr1_id}/")
        self.assertEqual(del_res.status_code, status.HTTP_200_OK)

        # Confirm address 2 was promoted to default
        get_addr2_after = self.client.get(f"/api/v1/customer/addresses/{addr2_id}/")
        self.assertEqual(get_addr2_after.status_code, status.HTTP_200_OK)
        self.assertTrue(get_addr2_after.data["data"]["is_default"])
