from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.users.models import User, MerchantStore, RiderProfile
from apps.customer.models import CustomerAddress
from apps.merchant.models import Order, Product


class Command(BaseCommand):
    help = "Seed initial realistic data for TiBoutik Admin Panel"

    def handle(self, *args, **options):
        self.stdout.write("Seeding platform administration data...")

        # 1. Admin User
        admin_user, created = User.objects.get_or_create(
            email="admin@wimi.com",
            defaults={
                "phone": "+50937009999",
                "full_name": "Super Administrator",
                "role": User.ROLE_ADMIN,
                "is_staff": True,
                "is_superuser": True,
                "is_verified": True,
                "is_active": True,
            },
        )
        if created:
            admin_user.set_password("Admin123!")
            admin_user.save()
            self.stdout.write(self.style.SUCCESS("Created Super Admin user."))

        # 2. Customers
        customers_data = [
            ("Marie Jean-Baptiste", "marie.jb@gmail.com", "+50948123456", False, ""),
            ("Pierre Dessalines", "pierre.d@yahoo.com", "+50937129900", False, ""),
            ("Claudette Moreau", "cmoreau@hotmail.com", "+50949102211", False, ""),
            ("Roosevelt Théodore", "rtheo@gmail.com", "+50938004455", False, ""),
            ("Nathalie Casimir", "ncasimir@outlook.com", "+50936118822", False, ""),
            ("Jean-Marc Lafortune", "jmlafortune@gmail.com", "+50947201199", False, ""),
            ("Sophie Beaumont", "sbeaumont@gmail.com", "+50939023344", False, ""),
            ("Lucner Augustin", "laugustin@yahoo.com", "+50944005511", True, "Suspected fraudulent chargeback activity and unauthorized card use"),
            ("Fabienne Voltaire", "fvoltaire@gmail.com", "+50933221100", True, "Repeated delivery cancellations and driver harassment reported"),
        ]

        for name, email, phone, banned, reason in customers_data:
            user, _ = User.objects.get_or_create(
                email=email,
                defaults={
                    "phone": phone,
                    "full_name": name,
                    "role": User.ROLE_CUSTOMER,
                    "is_active": not banned,
                    "is_banned": banned,
                    "ban_reason": reason,
                    "is_verified": True,
                },
            )
            # Add an address
            CustomerAddress.objects.get_or_create(
                user=user,
                label=CustomerAddress.LABEL_HOME,
                defaults={
                    "street_address": "15 Rue Capois, Champ de Mars",
                    "city": "Port-au-Prince",
                    "is_default": True,
                },
            )

        self.stdout.write(self.style.SUCCESS("Seeded customer accounts."))

        # 3. Merchants & Stores
        merchants_data = [
            {
                "owner_name": "Jacques Pétion",
                "email": "marche@gmail.com",
                "phone": "+50948001122",
                "store_name": "Marché Pétion",
                "category": MerchantStore.CATEGORY_GROCERY,
                "status": "Active",
                "reg": "HT-PAT-2023-441",
                "address": "14 Rue Faubert, Pétion-Ville",
                "wallet": Decimal("24800.00"),
            },
            {
                "owner_name": "Rosemonde Hyppolite",
                "email": "foodzone@gmail.com",
                "phone": "+50937108877",
                "store_name": "FoodZone Haiti",
                "category": MerchantStore.CATEGORY_RESTAURANT,
                "status": "Pending Verification",
                "reg": "HT-PAT-2024-092",
                "address": "Boulevard du 15 Octobre, Tabarre",
                "wallet": Decimal("0.00"),
            },
            {
                "owner_name": "Henri Christophe Jr.",
                "email": "boulangerie@gmail.com",
                "phone": "+50949112233",
                "store_name": "Boulangerie Citadelle",
                "category": MerchantStore.CATEGORY_BAKERY,
                "status": "Active",
                "reg": "HT-PAT-2023-882",
                "address": "Route de Delmas 48",
                "wallet": Decimal("9200.00"),
            },
            {
                "owner_name": "Virginie Laborde",
                "email": "epicerie@gmail.com",
                "phone": "+50938003344",
                "store_name": "Épicerie Laborde",
                "category": MerchantStore.CATEGORY_GROCERY,
                "status": "Suspended",
                "reg": "HT-PAT-2023-110",
                "address": "Delmas 75, Impasse Citadelle",
                "wallet": Decimal("6500.00"),
                "suspension_reason": "Store sanitary permit expired. Awaiting re-inspection report.",
            },
            {
                "owner_name": "Emmanuel Sainvil",
                "email": "techsote@gmail.com",
                "phone": "+50936224455",
                "store_name": "TechStore PaP",
                "category": MerchantStore.CATEGORY_BOUTIQUE,
                "status": "Pending Verification",
                "reg": "HT-PAT-2024-551",
                "address": "Rue Panaméricaine, Pétion-Ville",
                "wallet": Decimal("0.00"),
            },
            {
                "owner_name": "Carline Duvalier",
                "email": "pharma@gmail.com",
                "phone": "+50947009988",
                "store_name": "Phamarcéia Duvalier",
                "category": MerchantStore.CATEGORY_PHARMACY,
                "status": "Rejected",
                "reg": "HT-PAT-2024-998",
                "address": "Carrefour Feuilles, Rue Mgr Guilloux",
                "wallet": Decimal("0.00"),
                "rejection_reason": "Ministry of Public Health authorization license document was invalid or expired.",
            },
        ]

        created_stores = []
        for m in merchants_data:
            m_user, _ = User.objects.get_or_create(
                email=m["email"],
                defaults={
                    "phone": m["phone"],
                    "full_name": m["owner_name"],
                    "role": User.ROLE_MERCHANT,
                    "is_active": True,
                    "is_verified": True,
                },
            )
            if not m_user.has_usable_password():
                m_user.set_password("Password123!")
                m_user.save(update_fields=["password"])
            store, _ = MerchantStore.objects.get_or_create(
                owner=m_user,
                defaults={
                    "name": m["store_name"],
                    "category": m["category"],
                    "status": m["status"],
                    "reg_number": m["reg"],
                    "address": m["address"],
                    "wallet_balance": m["wallet"],
                    "rejection_reason": m.get("rejection_reason", ""),
                    "suspension_reason": m.get("suspension_reason", ""),
                    "is_verified": m["status"] == "Active",
                    "is_open": m["status"] == "Active",
                },
            )
            created_stores.append(store)

        self.stdout.write(self.style.SUCCESS("Seeded merchant stores."))

        # 4. Riders
        riders_data = [
            {
                "name": "Jean Louis",
                "email": "jean.louis.rider@wimi.com",
                "phone": "+50948012233",
                "zone": "Port-au-Prince Centre",
                "vehicle": "Motorcycle",
                "status": "Active",
                "deliveries": 312,
                "earnings": Decimal("87400.00"),
                "wallet": Decimal("6500.00"),
                "plate": "HT-2023-JL1",
            },
            {
                "name": "Michel Acé",
                "email": "michel.ace@wimi.com",
                "phone": "+50937148899",
                "zone": "Delmas",
                "vehicle": "Motorcycle",
                "status": "On Delivery",
                "deliveries": 189,
                "earnings": Decimal("52100.00"),
                "wallet": Decimal("4100.00"),
                "plate": "HT-2023-MA2",
            },
            {
                "name": "Frantz Romain",
                "email": "frantz.romain@wimi.com",
                "phone": "+50949203344",
                "zone": "Pétion-Ville",
                "vehicle": "Bicycle",
                "status": "Offline",
                "deliveries": 76,
                "earnings": Decimal("18900.00"),
                "wallet": Decimal("1890.00"),
                "plate": "HT-2024-FR3",
            },
            {
                "name": "Claudine Toussaint",
                "email": "claudine.t@wimi.com",
                "phone": "+50938116655",
                "zone": "Carrefour",
                "vehicle": "Motorcycle",
                "status": "Pending Verification",
                "deliveries": 0,
                "earnings": Decimal("0.00"),
                "wallet": Decimal("0.00"),
                "plate": "HT-2024-CT4",
            },
            {
                "name": "Wilder Pierre",
                "email": "wilder.pierre@wimi.com",
                "phone": "+50947114422",
                "zone": "Tabarre",
                "vehicle": "Motorcycle",
                "status": "Suspended",
                "deliveries": 44,
                "earnings": Decimal("11200.00"),
                "wallet": Decimal("950.00"),
                "plate": "HT-2024-WP5",
                "suspension_reason": "Multiple customer reports of route deviation and delayed delivery deliveries.",
            },
        ]

        for r in riders_data:
            r_user, _ = User.objects.get_or_create(
                email=r["email"],
                defaults={
                    "phone": r["phone"],
                    "full_name": r["name"],
                    "role": User.ROLE_RIDER,
                    "is_active": True,
                    "is_verified": True,
                },
            )
            if not r_user.has_usable_password():
                # Provide demo password (Admin123! for Jean Louis and Michel Ace; Password123! for others)
                demo_pwd = "Admin123!" if r["email"] in ["jean.louis.rider@wimi.com", "michel.ace@wimi.com"] else "Password123!"
                r_user.set_password(demo_pwd)
                r_user.save(update_fields=["password"])
            RiderProfile.objects.get_or_create(
                user=r_user,
                defaults={
                    "vehicle_type": r["vehicle"],
                    "number_plate": r["plate"],
                    "zone": r["zone"],
                    "status": r["status"],
                    "deliveries_count": r["deliveries"],
                    "total_earnings": r["earnings"],
                    "wallet_balance": r["wallet"],
                    "submission_date": timezone.now().date(),
                    "submission_id": f"SUB-2024-{r['name'][:2].upper()}01",
                    "front_face_photo": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=300&auto=format&fit=crop&q=80",
                    "left_face_photo": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=300&auto=format&fit=crop&q=80",
                    "right_face_photo": "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=300&auto=format&fit=crop&q=80",
                    "suspension_reason": r.get("suspension_reason", ""),
                },
            )

        self.stdout.write(self.style.SUCCESS("Seeded rider fleet and KYC profiles."))

        # 5. Sample Products & Orders
        sample_customer = User.objects.filter(role=User.ROLE_CUSTOMER, is_banned=False).first()
        if created_stores and sample_customer:
            first_store = created_stores[0]
            # Add products
            prod1, _ = Product.objects.get_or_create(
                store=first_store,
                sku="RIZ-NAT-5KG",
                defaults={
                    "name": "Riz National 5kg",
                    "category": "Grains",
                    "price": Decimal("350.00"),
                    "stock": 120,
                },
            )
            prod2, _ = Product.objects.get_or_create(
                store=first_store,
                sku="HAR-ROU-2KG",
                defaults={
                    "name": "Haricots Rouges 2kg",
                    "category": "Grains",
                    "price": Decimal("300.00"),
                    "stock": 80,
                },
            )

            # Add sample Order
            Order.objects.get_or_create(
                order_number="TBK-1041",
                defaults={
                    "store": first_store,
                    "customer": sample_customer,
                    "customer_name": sample_customer.full_name,
                    "customer_email": sample_customer.email,
                    "customer_phone": sample_customer.phone,
                    "delivery_address": "15 Rue Capois, Port-au-Prince",
                    "subtotal": Decimal("750.00"),
                    "delivery_fee": Decimal("100.00"),
                    "total_amount": Decimal("850.00"),
                    "status": "delivered",
                },
            )

        self.stdout.write(self.style.SUCCESS("Seeding complete!"))

