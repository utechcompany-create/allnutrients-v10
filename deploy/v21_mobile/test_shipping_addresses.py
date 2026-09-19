"""Run only against a disposable database, never the live store."""
import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
temporary = tempfile.TemporaryDirectory(prefix='v21-addresses-')
os.environ.update(DATABASE_URL='sqlite:///' + str(Path(temporary.name)/'test.db'),
                  APP_ENV='development', SESSION_COOKIE_SECURE='false',
                  ADMIN_EMAIL='address-admin@example.test', ADMIN_PASSWORD='LocalAdmin!234')
from app.db import Base, engine
from app import models
Base.metadata.create_all(engine)  # Simulate upgrading an existing database.
from app import main
from sqlalchemy import inspect
from fastapi.testclient import TestClient
main.seed()
main.seed()
assert 'shipping_addresses' in inspect(engine).get_table_names()
owner, other, admin, guest = (TestClient(main.app) for _ in range(4))
for client, email in ((owner,'owner@example.test'), (other,'other@example.test')):
    assert client.post('/api/auth/register',json={'email':email,'name':'배송지 고객','password':'LocalMember!234'}).status_code == 200
assert admin.post('/api/auth/login',json={'email':'address-admin@example.test','password':'LocalAdmin!234'}).status_code == 200
headers = lambda c: {'x-csrf-token':c.cookies.get('allnutrients_csrf')}
address = {'customerName':' 테스트 고객 ', 'customerPhone':'010-0000-0000', 'postcode':'12345',
           'address1':'테스트 도로 1', 'address2':'101호', 'deliveryMemo':'문 앞'}
path = '/api/shipping-addresses'
assert guest.get(path).status_code == 401
assert guest.post(path,json=address).status_code == 401
assert owner.post(path,json=address).status_code == 403
assert owner.post(path,json={**address,'userId':'other'},headers=headers(owner)).status_code == 422
assert owner.post(path,json={**address,'customerName':'  '},headers=headers(owner)).status_code == 422
saved = owner.post(path,json=address,headers=headers(owner))
assert saved.status_code == 200, saved.text
assert saved.headers['cache-control'] == 'private, no-store'
address_id = saved.json()['id']
assert saved.json()['customerName'] == '테스트 고객'
assert 'userId' not in saved.json()
again = owner.post(path,json={**address,'customerPhone':'01000000000','deliveryMemo':'배송 전 연락'},headers=headers(owner))
assert again.json()['id'] == address_id
assert len(owner.get(path).json()) == 1
assert owner.get(path).headers['cache-control'] == 'private, no-store'
for client in (other,admin):
    assert client.get(path).json() == []
    assert client.delete(path+'/'+address_id,headers=headers(client)).status_code == 404
assert owner.delete(path+'/'+address_id).status_code == 403

def save_parallel(_):
    response = owner.post(path,json={**address,'address2':'동시 저장'},headers=headers(owner))
    assert response.status_code == 200, response.text
    return response.json()['id']
with ThreadPoolExecutor(max_workers=4) as pool:
    assert len(set(pool.map(save_parallel,range(4)))) == 1
assert len(owner.get(path).json()) == 2

def order(client, **changes):
    body = {**address,'customerName':'주문 고객','customerEmail':'guest@example.test',
            'items':[{'productId':'P1001','qty':1}], 'paymentMethod':'CASH', 'guestPin':'1234', **changes}
    return client.post('/api/orders',json=body,headers=headers(client) if client is not guest else {})

response = order(owner,saveShippingAddress=True,address2='재주문용 상세주소')
assert response.status_code == 200,response.text
assert response.json()['shippingAddressSaved'] is True
order_no = response.json()['orderNo']
selected = next(a for a in owner.get(path).json() if a['address2'] == '재주문용 상세주소')
assert selected['customerPhone'] == address['customerPhone']
count = len(owner.get(path).json())
assert order(owner,saveShippingAddress=False,address2='저장하지 않음').status_code == 200
assert len(owner.get(path).json()) == count
assert order(owner,saveShippingAddress=True,items=[{'productId':'missing','qty':1}],address2='실패한 주문').status_code == 409
assert len(owner.get(path).json()) == count
assert order(guest,saveShippingAddress=True,address2='비회원 주소').status_code == 200
assert len(owner.get(path).json()) == count
assert owner.delete(path+'/'+selected['id'],headers=headers(owner)).status_code == 200
assert owner.get('/api/orders/'+order_no).json()['address2'] == '재주문용 상세주소'
assert selected['id'] not in {a['id'] for a in owner.get(path).json()}
while len(owner.get(path).json()) < 20:
    n = len(owner.get(path).json())
    r = owner.post(path,json={**address,'address2':'주소 '+str(n)},headers=headers(owner))
    assert r.status_code == 200,r.text
assert owner.post(path,json={**address,'address2':'초과 주소'},headers=headers(owner)).status_code == 409
full = order(owner,saveShippingAddress=True,address2='저장 한도 초과 주문')
assert full.status_code == 200,full.text
assert full.json()['shippingAddressSaved'] is False
assert len(owner.get(path).json()) == 20
assert owner.post(path,json=address,headers=headers(owner)).status_code == 200
print('PASS: upgrade, owner isolation, CSRF, validation, concurrent deduplication, order save/opt-out/rollback, guest exclusion, cap and immutable order addresses')
