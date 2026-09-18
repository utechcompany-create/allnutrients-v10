import os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "v21_test.db"
DB.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = "sqlite:///" + str(DB)
os.environ["APP_ENV"] = "development"
os.environ["SESSION_COOKIE_SECURE"] = "false"
os.environ["ADMIN_EMAIL"] = "admin@allnutrients.local"
os.environ["ADMIN_PASSWORD"] = "ChangeMe!2026"
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
import app.main as m

m.seed()
admin = TestClient(m.app)
assert admin.post("/api/auth/login", json={"email": "admin@allnutrients.local", "password": "ChangeMe!2026"}).status_code == 200
AH = {"x-csrf-token": admin.cookies.get("allnutrients_csrf")}

product = admin.post("/api/admin/products", headers=AH, json={
    "code": "V21-RETURN", "name": "V21 반품정책 상품", "category": "테스트", "price": 10000,
    "compareAt": 0, "stock": 100, "status": "판매중", "origin": "대한민국", "capacity": "테스트",
    "description": "V21", "emoji": "📦", "image": "", "detailTitle": "", "detailText": "", "detailImages": [],
    "options": [{"name": "2개입 박스", "price": 10000, "active": True, "sortOrder": 0,
                 "bundleAllowed": True, "bundleCapacity": 2}],
    "shippingType": "FIXED", "shippingFee": 3000, "returnFee": 4000, "exchangeFee": 5000,
    "bundleAllowed": True,
})
assert product.status_code == 200, product.text
product = product.json(); option = product["options"][0]

member = TestClient(m.app)
email = "v21@example.com"
assert member.post("/api/auth/register", json={"email": email, "password": "TestPass!234", "name": "V21회원"}).status_code == 200
MH = {"x-csrf-token": member.cookies.get("allnutrients_csrf")}

def delivered_order(qty, tag):
    res = member.post("/api/orders", headers=MH, json={
        "items": [{"productId": product["id"], "optionId": option["id"], "qty": qty}],
        "paymentMethod": "CASH", "customerName": "V21회원", "customerEmail": email,
        "customerPhone": "01012345678", "postcode": "06236", "address1": "서울 강남구",
        "address2": tag, "deliveryMemo": "", "cashDepositor": "V21", "couponId": "", "pointsToUse": 0,
    })
    assert res.status_code == 200, res.text
    no = res.json()["orderNo"]
    assert admin.post(f"/api/admin/orders/{no}/cash-paid", headers=AH, json={"note": "paid"}).status_code == 200
    assert admin.put(f"/api/admin/orders/{no}/shipment", headers=AH, json={"carrier": "CJ", "trackingNumber": tag, "status": "SHIPPED", "memo": ""}).status_code == 200
    return member.get("/api/orders/" + no).json()

def request_return(order, reason, qty):
    item = order["items"][0]
    res = member.post("/api/returns", headers=MH, json={
        "orderNo": order["orderNo"], "requestType": "RETURN", "reasonCode": reason,
        "reasonDetail": reason, "customerNote": "", "items": [{"orderItemId": item["orderItemId"], "qty": qty}],
        "attachments": [], "refundBankName": "테스트", "refundBankAccount": "123", "refundBankHolder": "회원",
    })
    assert res.status_code == 200, res.text
    return res.json()

partial = request_return(delivered_order(4, "V21-PARTIAL"), "CHANGE_MIND", 2)
assert partial["returnShippingFee"] == 2000 and partial["refundAmount"] == 18000, partial

full = request_return(delivered_order(2, "V21-FULL"), "CHANGE_MIND", 2)
assert full["returnShippingFee"] == 4000 and full["refundAmount"] == 16000, full

defect = request_return(delivered_order(2, "V21-DEFECT"), "DEFECT", 2)
assert defect["returnShippingFee"] == 0 and defect["refundAmount"] == 20000, defect

ui = (ROOT / "static/return-request.html").read_text()
request_script = ROOT / "static/assets/return-request.js"
if request_script.exists():
    ui += request_script.read_text()
for marker in ["data-capacity", "isPartialOneBox", "차감 없이 전액 환불", "1박스 분량 부분 반품 50%"]:
    assert marker in ui, marker
assert member.get("/api/health").json()["version"] == "21.0"
print({"version": "21.0", "partialFee": partial["returnShippingFee"], "fullFee": full["returnShippingFee"], "defectFee": defect["returnShippingFee"]})
