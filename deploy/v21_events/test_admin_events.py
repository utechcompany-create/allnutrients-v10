"""Unread lifecycle tests on an isolated SQLite database."""
import os
import sys
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

ROOT=Path(__file__).resolve().parent
os.chdir(ROOT);sys.path.insert(0,str(ROOT))
temp=tempfile.TemporaryDirectory(prefix='v21-events-')
os.environ.update(DATABASE_URL='sqlite:///'+str(Path(temp.name)/'test.db'),APP_ENV='development',
                  SESSION_COOKIE_SECURE='false',ADMIN_EMAIL='events-admin@example.test',ADMIN_PASSWORD='LocalAdmin!234')
from app.db import Base,engine,SessionLocal
from app.models import User,BoardPost
from app.security import hash_password
Base.metadata.create_all(engine)
with SessionLocal() as db:
    db.add(User(id='legacy',email='legacy@example.test',name='이전 고객',phone='',password_hash=hash_password('LocalMember!234'),role='customer',payment_customer_key='legacy-payment'))
    db.add(BoardPost(id='legacy-post',user_id='legacy',author='이전 고객',category='기타',title='이전 문의',content='이전 내용',status='답변대기',messages_json='[{"role":"seller","content":"답변"},{"role":"customer","content":"추가 질문"}]'))
    db.commit()
from app import main
from app.admin_events import AdminEvent,AdminRead
from fastapi.testclient import TestClient
from sqlalchemy import select,func
main.seed();main.seed()
admin,second,customer,guest=(TestClient(main.app) for _ in range(4))
assert admin.post('/api/auth/login',json={'email':'events-admin@example.test','password':'LocalAdmin!234'}).status_code==200
for client,name in ((second,'second'),(customer,'customer')):
    assert client.post('/api/auth/register',json={'email':name+'@example.test','name':name,'password':'LocalMember!234'}).status_code==200
second_id=second.get('/api/auth/me').json()['id']
with SessionLocal() as db:
    db.get(User,second_id).role='admin';db.commit()
admin_id=admin.get('/api/auth/me').json()['id']
headers=lambda c:{'x-csrf-token':c.cookies.get('allnutrients_csrf')}
count_path='/api/admin/event-counts';read_path='/api/admin/events/read'
counts=lambda c=admin:c.get(count_path).json()
def mark(client,kind,target,through,**extra):
    body={'adminId':client.get('/api/auth/me').json()['id'],'items':[{'kind':kind,'target':target,'through':through}],**extra}
    return client.post(read_path,headers=headers(client),json=body)
assert guest.get(count_path).status_code==401
assert customer.get(count_path).status_code==403
assert counts()['board']==2
assert admin.get(count_path).headers['cache-control']=='private, no-store'
assert admin.post(read_path,json={'adminId':admin_id,'items':[{'kind':'board','target':'legacy-post','through':3}]}).status_code==403
assert mark(customer,'board','legacy-post',3).status_code==403
assert mark(admin,'board','legacy-post',3).status_code==200
assert counts()['board']==0 and counts(second)['board']==2

direct=customer.post('/api/chat/rooms/direct',headers=headers(customer),json={}).json()['id']
assert counts()['directChat']==0  # Opening an empty room isn't an unread message.
def send(client,room,tag):
    r=client.post('/api/chat/rooms/'+room+'/messages',headers=headers(client),json={'content':tag,'clientId':tag})
    assert r.status_code==200,r.text
    return r.json()['id']
one=send(customer,direct,'one');two=send(customer,direct,'two')
send(customer,direct,'two')  # Same acknowledged send is not a second event.
send(admin,direct,'seller-reply')
customer.get('/api/chat/rooms');group=send(customer,'all','group-one')
assert counts()['directChat']==2 and counts()['groupChat']==1 and counts()['liveChat']==3
assert counts()['roomUnread'][direct]==2
assert mark(admin,'directChat',direct,one).status_code==200
assert counts()['directChat']==1 and counts(second)['directChat']==2
three=send(customer,direct,'arrived-during-read')
assert mark(admin,'directChat',direct,two).status_code==200
assert counts()['directChat']==1
assert mark(admin,'directChat',direct,one).status_code==200
assert counts()['directChat']==1  # A late older request cannot rewind the receipt.
assert mark(admin,'directChat',direct,three+100000).status_code==400
assert mark(admin,'directChat',direct,three,adminId=second_id).status_code==409
assert mark(admin,'groupChat','all',group).status_code==200
assert counts()['groupChat']==0 and counts()['directChat']==1
atomic=admin.post(read_path,headers=headers(admin),json={'adminId':admin_id,'items':[
    {'kind':'directChat','target':direct,'through':three}, {'kind':'board','target':'missing','through':1}]})
assert atomic.status_code==400 and counts()['directChat']==1
with ThreadPoolExecutor(max_workers=2) as pool:
    results=list(pool.map(lambda n:mark(admin,'directChat',direct,n).status_code,[three,one]))
assert results==[200,200] and counts()['directChat']==0

post=customer.post('/api/board',headers=headers(customer),json={'category':'일반문의','title':'비밀 문의','content':'개인 내용','isPrivate':True}).json()['id']
inquiry=customer.post('/api/inquiries',headers=headers(customer),json={'productId':'P1001','title':'상품 문의','content':'내용','isPrivate':True}).json()['id']
admin.post('/api/board',headers=headers(admin),json={'category':'기타','title':'공지','content':'관리자 작성'})
assert counts()['communications']==2
meta=admin.get('/api/admin/communications').json()
assert next(p for p in meta['board'] if p['id']==post)['unreadCount']==1
assert mark(admin,'board',post,1).status_code==200
assert counts()['communications']==1
admin.post('/api/admin/communications/board/'+post+'/reply',headers=headers(admin),json={'content':'답변'})
assert counts()['communications']==1
customer.post('/api/board/'+post+'/followup',headers=headers(customer),json={'content':'추가 질문'})
assert counts()['communications']==2
assert mark(admin,'board',post,1).status_code==200 and counts()['board']==1
meta=admin.get('/api/admin/communications').json()
row=next(p for p in meta['board'] if p['id']==post)
assert row['notificationThrough']==3 and row['unreadCount']==1
assert mark(admin,'board',post,3).status_code==200
assert mark(admin,'inquiry',inquiry,1).status_code==200
assert counts()['communications']==0
admin.post('/api/inquiries/'+inquiry+'/followup',headers=headers(admin),json={'content':'관리자 추가 안내'})
assert counts()['communications']==0
with SessionLocal() as db: before=db.scalar(select(func.count()).select_from(AdminEvent))
main.seed()
with SessionLocal() as db: assert db.scalar(select(func.count()).select_from(AdminEvent))==before
assert counts()['communications']==0 and counts(second)['communications']>0
print('PASS: legacy backfill, admin/CSRF isolation, message and thread events, own-write exclusion, read races, persistence, monotonic receipts, atomic batches and deduplication')
