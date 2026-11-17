import uuid
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from apps.merchant.models import MerchantStore, Order, OrderChatMessage, Product
from apps.users.models import RiderProfile

User = get_user_model()


class RiderAndCommunicationTests(TestCase):
    def setUp(self):
        # 1. Customer User
        self.customer = User.objects.create_user(
            email="customer@tiboutik.com",
            password="SecurePassword123!",
            full_name="Marie Jean-Baptiste",
            phone="+50938991122",
            role=User.ROLE_CUSTOMER,
        )

        # 2. Merchant User & Store
        self.merchant = User.objects.create_user(
            email="merchant@tiboutik.com",
            password="SecurePassword123!",
            full_name="Marché Pétion",
            role=User.ROLE_MERCHANT,
        )
        self.store = MerchantStore.objects.create(
            owner=self.merchant,
            name="Marché Pétion",
            category="Grocery",
            address="14 Rue Faubert, Pétion-Ville",
            phone="+50937124455",
            is_open=True,
        )

        # 3. Rider User & Profile
        self.rider_user = User.objects.create_user(
            email="rider@tiboutik.com",
            password="SecurePassword123!",
            full_name="Marc Antoine",
            phone="+50937001234",
            role=User.ROLE_RIDER,
        )
        self.rider_profile = RiderProfile.objects.create(
            user=self.rider_user,
            vehicle_type="Motorcycle",
            number_plate="HT-4432-MA",
            zone="Port-au-Prince Centre",
            status=RiderProfile.STATUS_ACTIVE,
            wallet_balance=Decimal("1000.00"),
            total_earnings=Decimal("5000.00"),
            deliveries_count=15,
        )

        # 4. Order created by Customer assigned to Rider
        self.order = Order.objects.create(
            store=self.store,
            order_number="#TBK-5544",
            customer=self.customer,
            customer_name="Marie Jean-Baptiste",
            customer_email="customer@tiboutik.com",
            customer_phone="+50938991122",
            delivery_address="15 Rue Capois, Port-au-Prince",
            delivery_method="Standard Delivery",
            subtotal=Decimal("500.00"),
            delivery_fee=Decimal("150.00"),
            total_amount=Decimal("650.00"),
            status=Order.STATUS_NEW,
            rider=self.rider_profile,
            otp_code="7788",
            delivery_step=0,
        )

        self.customer_client = APIClient()
        self.customer_client.force_authenticate(user=self.customer)

        self.rider_client = APIClient()
        self.rider_client.force_authenticate(user=self.rider_user)

    def test_rider_active_deliveries_and_step_progression(self):
        # 1. Rider fetches active deliveries
        res = self.rider_client.get("/api/v1/rider/deliveries/active/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["success"])
        self.assertEqual(len(res.data["data"]), 1)
        self.assertEqual(res.data["data"][0]["order_number"], "#TBK-5544")

        # 2. Rider advances step 0 -> 1 (Arrived at Store / Preparing)
        step1_res = self.rider_client.post(
            f"/api/v1/rider/deliveries/{self.order.id}/update/",
            data={"delivery_step": 1},
            format="json",
        )
        self.assertEqual(step1_res.status_code, status.HTTP_200_OK)
        self.order.refresh_from_db()
        self.assertEqual(self.order.delivery_step, 1)
        self.assertEqual(self.order.status, Order.STATUS_PREPARING)

        # 3. Rider advances step 1 -> 2 (Picked up / On the Way)
        step2_res = self.rider_client.post(
            f"/api/v1/rider/deliveries/{self.order.id}/update/",
            data={"delivery_step": 2},
            format="json",
        )
        self.assertEqual(step2_res.status_code, status.HTTP_200_OK)
        self.order.refresh_from_db()
        self.assertEqual(self.order.delivery_step, 2)
        self.assertEqual(self.order.status, Order.STATUS_ON_THE_WAY)

        # 4. Rider attempts verification with wrong OTP code -> Fails
        bad_otp_res = self.rider_client.post(
            f"/api/v1/rider/deliveries/{self.order.id}/verify-otp/",
            data={"otp_code": "9999"},
            format="json",
        )
        self.assertEqual(bad_otp_res.status_code, status.HTTP_400_BAD_REQUEST)

        # 5. Rider verifies with customer's real OTP code ("7788") -> Succeeds!
        verify_res = self.rider_client.post(
            f"/api/v1/rider/deliveries/{self.order.id}/verify-otp/",
            data={"otp_code": "7788"},
            format="json",
        )
        self.assertEqual(verify_res.status_code, status.HTTP_200_OK)
        self.order.refresh_from_db()
        self.rider_profile.refresh_from_db()

        self.assertEqual(self.order.status, Order.STATUS_DELIVERED)
        self.assertEqual(self.rider_profile.wallet_balance, Decimal("1150.00")) # 1000 + 150 fee
        self.assertEqual(self.rider_profile.deliveries_count, 16)

    def test_bidirectional_chat_between_customer_and_rider(self):
        # 1. Customer initiates chat by fetching message thread
        cust_get = self.customer_client.get(f"/api/v1/customer/orders/{self.order.id}/chat/")
        self.assertEqual(cust_get.status_code, status.HTTP_200_OK)
        self.assertTrue(len(cust_get.data["data"]) >= 1)

        # 2. Customer sends a message: "I am waiting at the blue gate"
        cust_post = self.customer_client.post(
            f"/api/v1/customer/orders/{self.order.id}/chat/",
            data={"message": "I am waiting at the blue gate"},
            format="json",
        )
        self.assertEqual(cust_post.status_code, status.HTTP_201_CREATED)
        self.assertEqual(cust_post.data["data"]["sender_role"], "customer")

        # 3. Rider opens chat and sees customer's message
        rider_get = self.rider_client.get(f"/api/v1/rider/deliveries/{self.order.id}/chat/")
        self.assertEqual(rider_get.status_code, status.HTTP_200_OK)
        messages_texts = [m["message"] for m in rider_get.data["data"]]
        self.assertIn("I am waiting at the blue gate", messages_texts)

        # 4. Rider replies: "Understood, pulling up now!"
        rider_reply = self.rider_client.post(
            f"/api/v1/rider/deliveries/{self.order.id}/chat/",
            data={"message": "Understood, pulling up now!"},
            format="json",
        )
        self.assertEqual(rider_reply.status_code, status.HTTP_201_CREATED)
        self.assertEqual(rider_reply.data["data"]["sender_role"], "rider")

        # 5. Customer fetches chat and receives rider's reply
        cust_refresh = self.customer_client.get(f"/api/v1/customer/orders/{self.order.id}/chat/")
        self.assertEqual(cust_refresh.status_code, status.HTTP_200_OK)
        customer_seen_texts = [m["message"] for m in cust_refresh.data["data"]]
        self.assertIn("Understood, pulling up now!", customer_seen_texts)

    def test_rider_accept_and_position_tracking_visible_to_customer(self):
        # 1. Create a fresh order for customer
        new_order = Order.objects.create(
            store=self.store,
            order_number="#TBK-9900",
            customer=self.customer,
            customer_name=self.customer.full_name,
            customer_email=self.customer.email,
            customer_phone=self.customer.phone,
            delivery_address="77 Rue Panamericaine, Petion-Ville",
            subtotal=Decimal("20.00"),
            delivery_fee=Decimal("2.00"),
            total_amount=Decimal("22.00"),
            status=Order.STATUS_NEW,
            rider=None,
        )

        # 2. Rider accepts the order with initial GPS coordinates
        accept_res = self.rider_client.post(
            f"/api/v1/rider/deliveries/{new_order.id}/accept/",
            data={"latitude": 18.5365, "longitude": -72.3385},
            format="json",
        )
        self.assertEqual(accept_res.status_code, status.HTTP_200_OK)

        # 3. Rider advances step to 2 (Out for Delivery) with new live GPS coordinates
        update_res = self.rider_client.post(
            f"/api/v1/rider/deliveries/{new_order.id}/update/",
            data={"delivery_step": 2, "latitude": 18.5445, "longitude": -72.3295},
            format="json",
        )
        self.assertEqual(update_res.status_code, status.HTTP_200_OK)

        # 4. Customer polls order tracking endpoint and sees rider position & status
        cust_res = self.customer_client.get(f"/api/v1/customer/orders/{new_order.id}/")
        self.assertEqual(cust_res.status_code, status.HTTP_200_OK)
        order_data = cust_res.data["data"]

        self.assertEqual(order_data["rider_name"], self.rider_user.full_name)
        self.assertEqual(order_data["delivery_step"], 2)
        self.assertIn("Out for Delivery", order_data["rider_status"])
        self.assertEqual(order_data["rider_latitude"], 18.5445)
        self.assertEqual(order_data["rider_longitude"], -72.3295)

    def test_rider_registration_pending_approval_and_admin_activation(self):
        # 1. Register a new delivery partner
        reg_client = APIClient()
        reg_payload = {
            "full_name": "Jean Baptiste Fleet",
            "email": "jb.fleet@tiboutik.com",
            "phone": "+50937998877",
            "password": "SecurePassword123!",
            "vehicle_type": "Motorcycle",
            "number_plate": "HT-9988-JB",
            "zone": "Delmas",
            "terms_accepted": True,
        }
        res = reg_client.post("/api/v1/auth/rider/register/", data=reg_payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data["success"])
        self.assertIn("pending administrator approval", res.data["message"])

        rider_profile = res.data["data"]["rider_profile"]
        self.assertEqual(rider_profile["status"], "Pending Verification")
        self.assertFalse(rider_profile["is_approved"])

        new_rider_token = res.data["data"]["access"]
        new_rider_client = APIClient()
        new_rider_client.credentials(HTTP_AUTHORIZATION=f"Bearer {new_rider_token}")

        # 2. While pending, rider cannot toggle online
        toggle_res = new_rider_client.post("/api/v1/rider/status/", data={"is_online": True}, format="json")
        self.assertEqual(toggle_res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("pending administrator approval", toggle_res.data["message"])

        # 3. Create platform admin user to approve the rider
        admin_user = User.objects.create_user(
            email="platform.admin@tiboutik.com",
            phone="+50937000001",
            password="AdminPassword123!",
            full_name="Platform Admin",
            role=User.ROLE_ADMIN,
            is_staff=True,
            is_superuser=True,
        )
        admin_client = APIClient()
        admin_client.force_authenticate(user=admin_user)

        # Admin approves the rider
        verify_res = admin_client.post(f"/api/v1/admin/riders/{rider_profile['id']}/verify/")
        self.assertEqual(verify_res.status_code, status.HTTP_200_OK)
        self.assertEqual(verify_res.data["data"]["status"], "Active")

        # 4. Now the rider can toggle online successfully
        toggle_active_res = new_rider_client.post("/api/v1/rider/status/", data={"is_online": True}, format="json")
        self.assertEqual(toggle_active_res.status_code, status.HTTP_200_OK)
        self.assertTrue(toggle_active_res.data["data"]["is_online"])
        self.assertEqual(toggle_active_res.data["data"]["status"], "Active")

