"""Purchase authorization, photo privacy, moderation and unread regression tests."""
import os
import sys
import tempfile
import io
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT);sys.path.insert(0, str(ROOT))
temp = tempfile.TemporaryDirectory(prefix='v21-review-test-')
os.environ.update(DATABASE_URL='sqlite:///' + str(Path(temp.name)/'test.db'), APP_ENV='development',
                  SESSION_COOKIE_SECURE='false', ADMIN_EMAIL='review-admin@example.test', ADMIN_PASSWORD='LocalAdmin!234')
from app import main, reviews
from app.db import SessionLocal
from app.models import User, Order, OrderItem, Shipment
from fastapi.testclient import TestClient
from sqlalchemy import select, func
main.seed()
admin, alice, bob, guest = [TestClient(main.app) for _ in range(4)]
assert admin.post('/api/auth/login', json={'email':'review-admin@example.test','password':'LocalAdmin!234'}).status_code == 200
for client, name in ((alice,'김구매자'),(bob,'이구매자')):
    assert client.post('/api/auth/register',json={'email':('alice' if client is alice else 'bob')+'@example.test','name':name,'password':'LocalMember!234'}).status_code == 200
aid = alice.get('/api/auth/me').json()['id'];bid = bob.get('/api/auth/me').json()['id']
headers = lambda c: {'x-csrf-token': c.cookies.get('allnutrients_csrf')}
def item(user, payment='PAID', status='DELIVERED', shipment=None):
    with SessionLocal() as db:
        number = str(db.scalar(select(func.count()).select_from(Order))+1)
        o = Order(id='order-'+number,order_no='ORDER-'+number,user_id=user,total_amount=10000,payment_method='CASH',payment_status=payment,order_status=status,customer_name='고객',customer_email='private@example.test',customer_phone='01000000000',address1='개인 주소')
        db.add(o);db.flush()
        i = OrderItem(order_id=o.id,product_id='P1001',product_name='코코넛워터 · 1박스',unit_price=10000,quantity=1,line_total=10000)
        db.add(i)
        if shipment: db.add(Shipment(order_id=o.id,status=shipment))
        db.commit();return i.id
good = item(aid);other = item(bid);pending = item(aid,'PENDING');shipping = item(aid,status='SHIPPED');canceled = item(aid,status='CANCELED',shipment='DELIVERED');returned = item(aid,'REFUNDED','RETURNED','DELIVERED')
payload = lambda n, **kw: {'orderItemId':n,'rating':5,'content':'포장이 꼼꼼하고 맛있어요.',**kw}
post = lambda c,n,**kw:c.post('/api/reviews',headers=headers(c),json=payload(n,**kw))
assert guest.get('/api/reviews/purchases').status_code == 401
assert admin.get('/api/reviews/purchases').status_code == 403
assert alice.get('/api/admin/reviews').status_code == 403
assert alice.post('/api/reviews',json=payload(good)).status_code == 403
assert post(bob,good).status_code == 404
for n in (pending,shipping,canceled): assert post(alice,n).status_code == 409
for change in ({'rating':0},{'rating':6},{'rating':1.5},{'content':'     '},{'photoIds':['fake']*6}):
    assert post(alice,good,**change).status_code == 422
listed = alice.get('/api/reviews/purchases').json()
assert {i['orderItemId'] for i in listed['items']} == {good,returned}

buffer=io.BytesIO();image=Image.new('RGB',(2100,1000),'green');exif=Image.Exif();exif[270]='private EXIF note';image.save(buffer,format='JPEG',exif=exif)
def photo(client,n,raw=buffer.getvalue()):
    return client.post('/api/review-photos',headers=headers(client),data={'orderItemId':n},files={'file':('photo.jpg',raw,'image/jpeg')})
assert photo(bob,good).status_code == 404
assert photo(alice,pending).status_code == 409
assert photo(alice,good,b'<svg><script>alert(1)</script></svg>').status_code == 400
assert photo(alice,good,b'x'*(10*1024*1024+1)).status_code == 413
image1=photo(alice,good);assert image1.status_code==201,image1.text
p1=image1.json();assert guest.get(p1['url']).status_code==404
assert bob.get(p1['url']).status_code==404
normalized=Image.open(io.BytesIO(alice.get(p1['url']).content))
assert max(normalized.size)<=1600 and len(normalized.getexif())==0
assert guest.get('/uploads/.review-media/'+p1['id']+'.jpg').status_code==404
assert guest.get('/uploads/%2ereview-media/'+p1['id']+'.jpg').status_code==404
assert post(bob,other,photoIds=[p1['id']]).status_code == 400
assert post(alice,good,photoIds=[p1['id'],p1['id']]).status_code == 400
saved=post(alice,good,photoIds=[p1['id']]);assert saved.status_code==201,saved.text
r=saved.json();rid=r['id'];assert r['photos']==[p1]
assert post(alice,good).status_code==409
assert guest.get(p1['url']).status_code==200
assert alice.delete(p1['url'],headers=headers(alice)).status_code==404
public=guest.get('/api/reviews?productId=P1001').json()
assert public['total']==1 and public['average']==5.0 and public['items'][0]['author']=='김**'
assert 'private@example' not in str(public) and 'ORDER-' not in str(public) and aid not in str(public)
assert not {'revision','orderItemId','hiddenReason','userId'} & set(public['items'][0])
assert guest.get('/api/reviews?productId=P1001&limit=1000').status_code==422
assert alice.put('/api/reviews/'+rid,json={'rating':2,'content':'별로였어요.', 'revision':1}).status_code==403
assert bob.put('/api/reviews/'+rid,headers=headers(bob),json={'rating':2,'content':'다른 사람 글', 'revision':1}).status_code==404
assert bob.request('DELETE','/api/reviews/'+rid,headers=headers(bob),json={'revision':1}).status_code==404
counts=lambda:admin.get('/api/admin/event-counts').json()['reviews']
assert counts()==1
meta=admin.get('/api/admin/reviews?visibility=unread').json()['items'][0]
admin_id=admin.get('/api/auth/me').json()['id']
def mark(through):return admin.post('/api/admin/events/read',headers=headers(admin),json={'adminId':admin_id,'items':[{'kind':'reviews','target':rid,'through':through}]})
assert mark(1).status_code==200 and counts()==0
edited=alice.put('/api/reviews/'+rid,headers=headers(alice),json={'rating':2,'content':'배송이 늦어 아쉬웠어요.', 'revision':1,'photoIds':[p1['id']]}).json()
assert edited['revision']==2 and counts()==1
assert mark(1).status_code==200 and counts()==1
assert alice.put('/api/reviews/'+rid,headers=headers(alice),json={'rating':1,'content':'오래된 화면 수정', 'revision':1}).status_code==409
assert admin.post('/api/admin/reviews/'+rid+'/reply',headers=headers(admin),json={'revision':1,'content':'답변'}).status_code==409
assert admin.post('/api/admin/reviews/'+rid+'/reply',headers=headers(admin),json={'revision':2,'content':'구매 의견 감사합니다.'}).status_code==200
assert counts()==1  # Seller replies are not new buyer events.
assert guest.get('/api/reviews?productId=P1001').json()['items'][0]['reply']=='구매 의견 감사합니다.'
assert admin.patch('/api/admin/reviews/'+rid+'/visibility',headers=headers(admin),json={'revision':2,'hidden':True,'reason':''}).status_code==400
assert admin.patch('/api/admin/reviews/'+rid+'/visibility',headers=headers(admin),json={'revision':2,'hidden':True,'reason':'사진의 개인정보 노출'}).status_code==200
assert guest.get('/api/reviews?productId=P1001').json()['total']==0 and guest.get('/api/reviews?productId=P1001').json()['average'] is None
assert guest.get(p1['url']).status_code==404 and bob.get(p1['url']).status_code==404
assert alice.get(p1['url']).status_code==200 and admin.get(p1['url']).status_code==200
assert alice.get('/api/reviews/purchases').json()['items'][-1]['review']['hidden']
assert admin.get('/api/admin/reviews?visibility=hidden').json()['total']==1
assert admin.patch('/api/admin/reviews/'+rid+'/visibility',headers=headers(admin),json={'revision':2,'hidden':False}).status_code==200
assert guest.get(p1['url']).status_code==200
assert alice.request('DELETE','/api/reviews/'+rid,headers=headers(alice),json={'revision':2}).status_code==200
assert counts()==0 and guest.get(p1['url']).status_code==404 and alice.get(p1['url']).status_code==404
with SessionLocal() as db: assert db.get(reviews.ReviewPhoto, p1['id']) is None
assert mark(2).status_code==200  # A deleted review must not block other read acknowledgements.
assert post(alice,good).status_code==201
assert post(alice,returned,rating=1).status_code==201  # Refunds after delivery must not silence reviews.
duplicate=item(aid)
with ThreadPoolExecutor(max_workers=2) as pool:
    results=list(pool.map(lambda _:post(alice,duplicate).status_code,range(2)))
assert sorted(results)==[201,409],results
main.seed();assert guest.get('/api/reviews?productId=P1001&limit=1&offset=1').json()['total']==3
print('PASS: purchase/CSRF/ownership checks, duplicate concurrency, rating validation, photo normalization/privacy, revision safety, moderation, unread counters and pagination')
