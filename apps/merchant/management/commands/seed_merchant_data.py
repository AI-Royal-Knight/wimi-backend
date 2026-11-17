from decimal import Decimal
from django.core.management.base import BaseCommand
from apps.users.models import User, MerchantStore
from apps.merchant.models import Product, ProductVariant, Order, OrderItem, Transaction, PayoutRequest


class Command(BaseCommand):
    help = "Seed initial realistic merchant products, orders, and transactions"

    def handle(self, *args, **options):
        # Find merchant user
        user = User.objects.filter(email="jean.laurent@email.com").first()
        if not user:
            user = User.objects.filter(role="merchant").first()

        if not user:
            self.stdout.write(self.style.ERROR("No merchant user found to seed."))
            return

        store = getattr(user, "merchant_store", None)
        if not store:
            store = MerchantStore.objects.create(
                owner=user,
                name="Laurent Organic Market",
                category="Grocery",
                address="124 Rue de la Paix, Brazzaville",
                phone="+242 06 123 4567",
                description="Organic groceries, fresh bakery produce, and local farm goods.",
                bank_name="Chase Bank",
                account_number="4532",
                account_holder=user.full_name,
                routing_number="021000021",
            )
        else:
            if not store.bank_name:
                store.bank_name = "Chase Bank"
                store.account_number = "4532"
                store.account_holder = user.full_name
                store.routing_number = "021000021"
                store.save()

        self.stdout.write(f"Seeding data for store: {store.name}...")

        # 1. Products
        products_data = [
            {
                "name": "Organic Tomatoes",
                "category": "Vegetables",
                "sku": "VEG-001",
                "price": Decimal("5.00"),
                "stock": 89,
                "min_stock": 50,
                "max_stock": 200,
                "sold_count": 245,
                "status": "Active",
                "description": "Farm-fresh ripe red organic tomatoes grown without pesticides.",
                "image_url_fallback": "https://images.unsplash.com/photo-1596422846543-7ce3c530fd6f?w=400&q=80",
            },
            {
                "name": "Fresh Milk 1L",
                "category": "Dairy",
                "sku": "DAIRY-002",
                "price": Decimal("4.00"),
                "stock": 156,
                "min_stock": 100,
                "max_stock": 300,
                "sold_count": 198,
                "status": "Active",
                "description": "Whole pasture-raised cow milk, pasteurized and bottled fresh daily.",
                "image_url_fallback": "https://images.unsplash.com/photo-1550989460-0adf9ea622e2?w=400&q=80",
            },
            {
                "name": "Chicken Breast",
                "category": "Meat",
                "sku": "MEAT-003",
                "price": Decimal("10.00"),
                "stock": 45,
                "min_stock": 50,
                "max_stock": 150,
                "sold_count": 167,
                "status": "Low Stock",
                "description": "Tender skinless boneless chicken breast fillets.",
                "image_url_fallback": "https://images.unsplash.com/photo-1604503468506-a8da13d82791?w=400&q=80",
            },
            {
                "name": "Whole Wheat Bread",
                "category": "Bakery",
                "sku": "BAKERY-004",
                "price": Decimal("3.00"),
                "stock": 78,
                "min_stock": 80,
                "max_stock": 200,
                "sold_count": 143,
                "status": "Active",
                "description": "Artisan baked whole grain wheat bread with seeds.",
                "image_url_fallback": "https://images.unsplash.com/photo-1584916201218-f4242ceb4809?w=400&q=80",
            },
            {
                "name": "Greek Yogurt",
                "category": "Dairy",
                "sku": "DAIRY-005",
                "price": Decimal("5.00"),
                "stock": 92,
                "min_stock": 80,
                "max_stock": 250,
                "sold_count": 128,
                "status": "Active",
                "description": "Authentic strained thick Greek yogurt rich in protein.",
                "image_url_fallback": "https://images.unsplash.com/photo-1488477181946-6428a0291777?w=400&q=80",
            },
            {
                "name": "Fresh Eggs (12)",
                "category": "Dairy",
                "sku": "DAIRY-006",
                "price": Decimal("6.00"),
                "stock": 23,
                "min_stock": 100,
                "max_stock": 300,
                "sold_count": 156,
                "status": "Low Stock",
                "description": "Grade A cage-free brown eggs, carton of 12.",
                "image_url_fallback": "https://images.unsplash.com/photo-1598965402089-897ce52e8355?w=400&q=80",
            },
            {
                "name": "Organic Apples",
                "category": "Fruits",
                "sku": "FRUIT-007",
                "price": Decimal("4.50"),
                "stock": 68,
                "min_stock": 80,
                "max_stock": 200,
                "sold_count": 134,
                "status": "Active",
                "description": "Crisp sweet organic Gala apples picked at peak ripeness.",
                "image_url_fallback": "https://images.unsplash.com/photo-1560806887-1e4cd0b6faa6?w=400&q=80",
            },
            {
                "name": "Brown Rice 1kg",
                "category": "Grains",
                "sku": "GRAIN-008",
                "price": Decimal("8.00"),
                "stock": 0,
                "min_stock": 50,
                "max_stock": 150,
                "sold_count": 89,
                "status": "Out of Stock",
                "description": "Long grain nutritious whole brown rice in 1kg eco pack.",
                "image_url_fallback": "https://images.unsplash.com/photo-1586201375761-83865001e31c?w=400&q=80",
            },
        ]

        created_products = {}
        for pdata in products_data:
            p, _ = Product.objects.update_or_create(
                store=store,
                sku=pdata["sku"],
                defaults=pdata,
            )
            created_products[p.sku] = p

        # Variants for Tomatoes
        if "VEG-001" in created_products:
            p = created_products["VEG-001"]
            if not p.variants.exists():
                ProductVariant.objects.create(product=p, size="1kg", color="Red", stock=49, sku="VEG-001-1KG")
                ProductVariant.objects.create(product=p, size="500g", color="Red", stock=40, sku="VEG-001-500G")

        # 2. Orders
        orders_data = [
            {
                "order_number": "#ORD-12345",
                "customer_name": "Sarah Johnson",
                "customer_email": "sarah.johnson@email.com",
                "customer_phone": "+1 234 567 8900",
                "customer_avatar": "https://i.pravatar.cc/150?u=1",
                "delivery_address": "742 Evergreen Terrace, New York, NY",
                "delivery_method": "Standard Delivery",
                "estimated_delivery": "May 23, 2025 - May 25, 2025",
                "subtotal": Decimal("82.50"),
                "delivery_fee": Decimal("5.00"),
                "discount": Decimal("0.00"),
                "total_amount": Decimal("87.50"),
                "payment_method": "Cash on Delivery",
                "status": Order.STATUS_NEW,
                "items": [
                    {"product_name": "Fresh Tomatoes (1 kg)", "price": Decimal("25.00"), "quantity": 1, "image_url": "https://images.unsplash.com/photo-1596422846543-7ce3c530fd6f?w=100&q=80"},
                    {"product_name": "Organic Milk (1 L)", "price": Decimal("32.50"), "quantity": 1, "image_url": "https://images.unsplash.com/photo-1550989460-0adf9ea622e2?w=100&q=80"},
                    {"product_name": "Whole Wheat Bread", "price": Decimal("30.00"), "quantity": 1, "image_url": "https://images.unsplash.com/photo-1584916201218-f4242ceb4809?w=100&q=80"},
                ],
            },
            {
                "order_number": "#ORD-12344",
                "customer_name": "Rajesh Kumar",
                "customer_email": "rajesh.kumar@email.com",
                "customer_phone": "+1 234 567 8901",
                "customer_avatar": "https://i.pravatar.cc/150?u=2",
                "delivery_address": "128 Baker Street, Los Angeles, CA",
                "delivery_method": "Express Courier",
                "estimated_delivery": "May 22, 2025",
                "subtotal": Decimal("150.00"),
                "delivery_fee": Decimal("6.00"),
                "discount": Decimal("0.00"),
                "total_amount": Decimal("156.00"),
                "payment_method": "Card",
                "status": Order.STATUS_NEW,
                "items": [
                    {"product_name": "Chicken Breast", "price": Decimal("100.00"), "quantity": 2, "image_url": "https://images.unsplash.com/photo-1604503468506-a8da13d82791?w=100&q=80"},
                    {"product_name": "Greek Yogurt", "price": Decimal("56.00"), "quantity": 1, "image_url": "https://images.unsplash.com/photo-1488477181946-6428a0291777?w=100&q=80"},
                ],
            },
            {
                "order_number": "#ORD-12343",
                "customer_name": "Priya Sharma",
                "customer_email": "priya.sharma@email.com",
                "customer_phone": "+1 234 567 8902",
                "customer_avatar": "https://i.pravatar.cc/150?u=3",
                "delivery_address": "45 King's Cross Road, Chicago, IL",
                "delivery_method": "Standard Delivery",
                "estimated_delivery": "May 24, 2025",
                "subtotal": Decimal("87.80"),
                "delivery_fee": Decimal("5.00"),
                "discount": Decimal("0.00"),
                "total_amount": Decimal("92.80"),
                "payment_method": "Cash on Delivery",
                "status": Order.STATUS_NEW,
                "items": [
                    {"product_name": "Fresh Milk 1L", "price": Decimal("32.50"), "quantity": 2, "image_url": "https://images.unsplash.com/photo-1550989460-0adf9ea622e2?w=100&q=80"},
                    {"product_name": "Whole Wheat Bread", "price": Decimal("27.80"), "quantity": 1, "image_url": "https://images.unsplash.com/photo-1584916201218-f4242ceb4809?w=100&q=80"},
                ],
            },
            {
                "order_number": "#ORD-12342",
                "customer_name": "Mike Wilson",
                "customer_email": "mike.wilson@email.com",
                "customer_phone": "+1 234 567 8903",
                "customer_avatar": "https://i.pravatar.cc/150?u=4",
                "delivery_address": "902 Beverly Hills Drive, Los Angeles, CA",
                "delivery_method": "Standard Delivery",
                "estimated_delivery": "May 21, 2025",
                "subtotal": Decimal("198.50"),
                "delivery_fee": Decimal("5.00"),
                "discount": Decimal("0.00"),
                "total_amount": Decimal("203.50"),
                "payment_method": "Card",
                "status": Order.STATUS_PREPARING,
                "items": [
                    {"product_name": "Chicken Breast", "price": Decimal("100.00"), "quantity": 2, "image_url": "https://images.unsplash.com/photo-1604503468506-a8da13d82791?w=100&q=80"},
                    {"product_name": "Greek Yogurt", "price": Decimal("98.50"), "quantity": 2, "image_url": "https://images.unsplash.com/photo-1488477181946-6428a0291777?w=100&q=80"},
                ],
            },
            {
                "order_number": "#ORD-12341",
                "customer_name": "Amit Patel",
                "customer_email": "amit.patel@email.com",
                "customer_phone": "+1 234 567 8904",
                "customer_avatar": "https://i.pravatar.cc/150?u=5",
                "delivery_address": "12 Market Square, Houston, TX",
                "delivery_method": "Standard Delivery",
                "estimated_delivery": "May 21, 2025",
                "subtotal": Decimal("73.00"),
                "delivery_fee": Decimal("5.00"),
                "discount": Decimal("0.00"),
                "total_amount": Decimal("78.00"),
                "payment_method": "Card",
                "status": Order.STATUS_READY,
                "items": [
                    {"product_name": "Whole Wheat Bread", "price": Decimal("30.00"), "quantity": 1, "image_url": "https://images.unsplash.com/photo-1584916201218-f4242ceb4809?w=100&q=80"},
                    {"product_name": "Fresh Milk 1L", "price": Decimal("43.00"), "quantity": 1, "image_url": "https://images.unsplash.com/photo-1550989460-0adf9ea622e2?w=100&q=80"},
                ],
            },
            {
                "order_number": "#ORD-12340",
                "customer_name": "Emma Davis",
                "customer_email": "emma.davis@email.com",
                "customer_phone": "+1 234 567 8905",
                "customer_avatar": "https://i.pravatar.cc/150?u=6",
                "delivery_address": "88 Riverside Dr, Chicago, IL",
                "delivery_method": "Standard Delivery",
                "estimated_delivery": "May 20, 2025",
                "subtotal": Decimal("51.30"),
                "delivery_fee": Decimal("5.00"),
                "discount": Decimal("0.00"),
                "total_amount": Decimal("56.30"),
                "payment_method": "Cash on Delivery",
                "status": Order.STATUS_ON_THE_WAY,
                "items": [
                    {"product_name": "Whole Wheat Bread (2)", "price": Decimal("51.30"), "quantity": 2, "image_url": "https://images.unsplash.com/photo-1584916201218-f4242ceb4809?w=100&q=80"},
                ],
            },
            {
                "order_number": "#ORD-12339",
                "customer_name": "Lisa Brown",
                "customer_email": "lisa.brown@email.com",
                "customer_phone": "+1 234 567 8906",
                "customer_avatar": "https://i.pravatar.cc/150?u=7",
                "delivery_address": "334 Pine St, Houston, TX",
                "delivery_method": "Standard Delivery",
                "estimated_delivery": "May 19, 2025",
                "subtotal": Decimal("90.80"),
                "delivery_fee": Decimal("5.00"),
                "discount": Decimal("0.00"),
                "total_amount": Decimal("95.80"),
                "payment_method": "Card",
                "status": Order.STATUS_DELIVERED,
                "items": [
                    {"product_name": "Brown Rice (1)", "price": Decimal("45.00"), "quantity": 1, "image_url": "https://images.unsplash.com/photo-1586201375761-83865001e31c?w=100&q=80"},
                    {"product_name": "Fresh Eggs (2)", "price": Decimal("45.80"), "quantity": 2, "image_url": "https://images.unsplash.com/photo-1598965402089-897ce52e8355?w=100&q=80"},
                ],
            },
        ]

        for odata in orders_data:
            items_list = odata.pop("items")
            order, _ = Order.objects.update_or_create(
                store=store,
                order_number=odata["order_number"],
                defaults=odata,
            )
            order.items.all().delete()
            for itm in items_list:
                OrderItem.objects.create(order=order, **itm)

        # 3. Transactions & Lifetime Ledger
        transactions_data = [
            {"transaction_id": "TX-9821", "type": "withdrawal", "description": "Payout to Chase Bank ending in 4532", "amount": Decimal("1240.00"), "status": "Completed"},
            {"transaction_id": "TX-9820", "type": "earning", "description": "Order #ORD-12339 settlement", "amount": Decimal("95.80"), "status": "Completed"},
            {"transaction_id": "TX-9819", "type": "earning", "description": "Order #ORD-12344 settlement", "amount": Decimal("156.00"), "status": "Completed"},
            {"transaction_id": "TX-9818", "type": "earning", "description": "Order #ORD-12340 settlement", "amount": Decimal("56.30"), "status": "Pending"},
            {"transaction_id": "TX-9817", "type": "withdrawal", "description": "Payout to Chase Bank ending in 4532", "amount": Decimal("850.00"), "status": "Completed"},
            {"transaction_id": "TX-9000-BASE", "type": "earning", "description": "Prior marketplace settlements", "amount": Decimal("6838.20"), "status": "Completed"},
        ]

        for tx in transactions_data:
            Transaction.objects.update_or_create(
                store=store,
                transaction_id=tx["transaction_id"],
                defaults=tx,
            )

        self.stdout.write(self.style.SUCCESS("Successfully seeded merchant store data!"))
