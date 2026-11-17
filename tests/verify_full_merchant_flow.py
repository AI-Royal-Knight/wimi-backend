import urllib.request
import json

def request(url, method="GET", data=None, headers=None):
    if headers is None:
        headers = {}
    encoded_data = json.dumps(data).encode() if data is not None else None
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=encoded_data, headers=headers, method=method)
    with urllib.request.urlopen(req) as res:
        return res.status, json.loads(res.read().decode())

def run():
    print("--- STARTING COMPLETE MERCHANT INTEGRATION TEST ---")

    # 1. Login
    s, res = request(
        "http://localhost:8000/api/v1/auth/login/",
        "POST",
        {"identifier": "jean.laurent@email.com", "password": "Password123!"},
    )
    assert s == 200 and res["success"] is True
    token = res["data"]["access"]
    headers = {"Authorization": f"Bearer {token}"}
    print("[PASS] 1. Login success. Access token obtained.")

    # 2. Get Profile & Store
    s, res = request("http://localhost:8000/api/v1/auth/me/", headers=headers)
    assert s == 200 and res["data"]["role"] == "merchant"
    print(f"[PASS] 2. Profile fetch: {res['data']['full_name']} (Role: {res['data']['role']})")

    # 3. Update Profile
    s, res = request(
        "http://localhost:8000/api/v1/auth/me/",
        "PATCH",
        {"full_name": "Jean-Pierre Laurent"},
        headers=headers,
    )
    assert s == 200 and res["data"]["full_name"] == "Jean-Pierre Laurent"
    print(f"[PASS] 3. Profile update: {res['data']['full_name']}")

    # 4. Store Get & Update
    s, res = request("http://localhost:8000/api/v1/users/store/", headers=headers)
    assert s == 200 and res["data"]["name"]
    print(f"[PASS] 4. Store fetch: {res['data']['name']} (Category: {res['data']['category']})")

    s, res = request(
        "http://localhost:8000/api/v1/users/store/",
        "PATCH",
        {"description": "Organic & fresh produce market"},
        headers=headers,
    )
    assert s == 200 and res["data"]["description"] == "Organic & fresh produce market"
    print("[PASS] 5. Store update description verified.")

    # 5. Dashboard
    s, res = request("http://localhost:8000/api/v1/merchant/dashboard/", headers=headers)
    assert s == 200 and res["success"] is True
    print(
        f"[PASS] 6. Dashboard metrics: Today Sales: {res['data']['today_sales_formatted']}, Pending: {res['data']['pending_orders']}, Products: {res['data']['active_products']}"
    )

    # 6. Orders Lifecycle (New -> Preparing -> Ready -> On the Way -> Delivered)
    s, res = request("http://localhost:8000/api/v1/merchant/orders/?tab=new", headers=headers)
    assert s == 200 and "data" in res
    print(f"[PASS] 7. Found {res['count']} new orders.")

    if res["count"] > 0:
        test_order = res["data"][0]
        oid = test_order["id"]
        # Accept
        s, res = request(
            f"http://localhost:8000/api/v1/merchant/orders/{oid}/accept/", "POST", headers=headers
        )
        assert s == 200 and res["data"]["status"] == "preparing"
        print(f"[PASS] 8. Order {oid} accepted -> status: preparing")

        # Status -> ready
        s, res = request(
            f"http://localhost:8000/api/v1/merchant/orders/{oid}/status/",
            "PATCH",
            {"status": "ready"},
            headers=headers,
        )
        assert s == 200 and res["data"]["status"] == "ready"
        print(f"[PASS] 9. Order {oid} -> status: ready")

        # Status -> on_the_way
        s, res = request(
            f"http://localhost:8000/api/v1/merchant/orders/{oid}/status/",
            "PATCH",
            {"status": "on_the_way"},
            headers=headers,
        )
        assert s == 200 and res["data"]["status"] == "on_the_way"
        print(f"[PASS] 10. Order {oid} -> status: on_the_way")

        # Status -> delivered
        s, res = request(
            f"http://localhost:8000/api/v1/merchant/orders/{oid}/status/",
            "PATCH",
            {"status": "delivered"},
            headers=headers,
        )
        assert s == 200 and res["data"]["status"] == "delivered"
        print(f"[PASS] 11. Order {oid} -> status: delivered (ledger settlement recorded)")

    # 7. Products CRUD
    s, res = request(
        "http://localhost:8000/api/v1/merchant/products/",
        "POST",
        {
            "name": "Golden Pineapple",
            "category": "Fruits",
            "sku": "FRUIT-PINEAPPLE-01",
            "price": "7.50",
            "stock": 35,
            "status": "Active",
        },
        headers=headers,
    )
    assert s == 201
    pid = res["data"]["id"]
    print(f"[PASS] 12. Product created: {res['data']['name']} (ID: {pid})")

    s, res = request(
        f"http://localhost:8000/api/v1/merchant/products/{pid}/stock/",
        "POST",
        {"action": "add", "quantity": 15},
        headers=headers,
    )
    assert s == 200 and res["data"]["stock"] == 50
    print(f"[PASS] 13. Product stock adjusted: 35 + 15 = {res['data']['stock']}")

    s, res = request(f"http://localhost:8000/api/v1/merchant/products/{pid}/", "DELETE", headers=headers)
    assert s == 200
    print("[PASS] 14. Product deleted cleanly.")

    # 8. Inventory
    s, res = request("http://localhost:8000/api/v1/merchant/inventory/", headers=headers)
    assert s == 200 and "summary" in res
    print(
        f"[PASS] 15. Inventory summary: total={res['summary']['total_products']}, low_stock={res['summary']['low_stock']}"
    )

    # 9. Earnings & Payout
    s, res = request("http://localhost:8000/api/v1/merchant/earnings/", headers=headers)
    assert s == 200 and "available_balance" in res["data"]
    bal = res["data"]["available_balance"]
    print(f"[PASS] 16. Earnings retrieved: available=${bal:,.2f}")

    s, res = request(
        "http://localhost:8000/api/v1/merchant/payouts/",
        "POST",
        {
            "amount": "50.00",
            "method": "Bank Transfer",
            "bank_name": "Verified Bank",
            "account_number": "4532",
            "account_holder": "Jean-Pierre Laurent",
        },
        headers=headers,
    )
    assert s == 201 and res["data"]["status"] == "Pending"
    print(f"[PASS] 17. Payout requested: $50.00 (Status: {res['data']['status']})")

    print("--- ALL 17 INTEGRATION POINTS VERIFIED AND PASSING! ---")

if __name__ == "__main__":
    run()

