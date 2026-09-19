"""Sales accounting boundaries and private realtime chat on an isolated database."""
import asyncio
import csv
import io
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT);sys.path.insert(0,str(ROOT))
temporary=tempfile.TemporaryDirectory(prefix='v21-operations-')
os.environ.update(DATABASE_URL='sqlite:///'+str(Path(temporary.name)/'test.db'),APP_ENV='development',
                  SESSION_COOKIE_SECURE='false',ADMIN_EMAIL='operations-admin@example.test',ADMIN_PASSWORD='LocalAdmin!234')
from app.db import Base,engine,SessionLocal
from app.models import Order,ReturnRequest,AuthSession
Base.metadata.create_all(engine)  # Existing installation before new models are imported.
import app.main as main
from app import chat
from fastapi.testclient import TestClient
from sqlalchemy import delete,inspect
main.seed();main.seed()
assert {'chat_rooms','chat_messages'} <= set(inspect(engine).get_table_names())
admin,owner,other,anonymous=(TestClient(main.app) for _ in range(4))
assert admin.post('/api/auth/login',json={'email':'operations-admin@example.test','password':'LocalAdmin!234'}).status_code==200
for client,name in ((owner,'상담 고객'),(other,'다른 고객')):
    r=client.post('/api/auth/register',json={'email':('owner' if client is owner else 'other')+'@example.test','password':'LocalMember!234','name':name})
    assert r.status_code==200,r.text
uid=owner.get('/api/auth/me').json()['id'];other_id=other.get('/api/auth/me').json()['id']
headers=lambda client:{'x-csrf-token':client.cookies.get('allnutrients_csrf')}

def order(tag,amount,status,when='2026-08-31T15:00:00+00:00',**extra):
    return Order(id=tag,order_no='ORD-'+tag,user_id=uid,total_amount=amount,payment_method='CARD',payment_status=status,
                 customer_name='=SUM(1,2)',customer_email='owner@example.test',customer_phone='01000000000',address1='테스트 주소',
                 created_at=datetime.fromisoformat(when),**extra)

with SessionLocal() as db:
    db.add_all([order('paid',10000,'PAID'),order('partial',15000,'PARTIAL_REFUNDED'),order('full',20000,'REFUNDED'),
                order('waiting-refund',7000,'REFUND_PENDING'),order('unpaid',5000,'PENDING'),
                order('before',8000,'PAID','2026-08-31T14:59:59+00:00'),order('after',9000,'PAID','2026-09-01T15:00:00+00:00')])
    db.commit()
    db.add_all([ReturnRequest(id='r1',request_no='R1',order_id='partial',request_type='RETURN',refund_status='COMPLETED',refund_amount=5000),
                ReturnRequest(id='r2',request_no='R2',order_id='partial',request_type='RETURN',refund_status='APPROVED',refund_amount=1000),
                ReturnRequest(id='r3',request_no='R3',order_id='partial',request_type='EXCHANGE',refund_status='COMPLETED',refund_amount=15000)])
    db.commit()
q='?start=2026-09-01&end=2026-09-01'
for path in ('/api/admin/sales','/api/admin/sales/export.csv'):
    assert anonymous.get(path+q).status_code==401
    assert owner.get(path+q).status_code==403
report=admin.get('/api/admin/sales'+q)
assert report.status_code==200,report.text
assert report.headers['cache-control']=='private, no-store'
assert report.json()['totals']=={'orderCount':4,'grossAmount':52000,'refundAmount':25000,'netAmount':27000},report.json()
assert report.json()['daily'][0]['date']=='2026-09-01'
assert {r['orderNo'] for r in report.json()['orders']}=={'ORD-paid','ORD-partial','ORD-full','ORD-waiting-refund'}
for bad in ('?start=wrong','?start=2026-09-02&end=2026-09-01','?start=2020-01-01&end=2026-09-01'):
    assert admin.get('/api/admin/sales'+bad).status_code==400
export=admin.get('/api/admin/sales/export.csv'+q)
assert export.status_code==200 and export.content.startswith(b'\xef\xbb\xbf')
rows=list(csv.reader(io.StringIO(export.content.decode('utf-8-sig'))))
assert len(rows)==5 and rows[0][0]=='주문일(한국시간)'
assert all(row[2]=="'=SUM(1,2)" and row[3]=='신용·체크카드' for row in rows[1:])
assert sum(int(row[-1]) for row in rows[1:])==27000
with SessionLocal() as db:
    db.add(order('pg-unknown',12000,'PARTIAL_CANCELED',payment_key='synthetic-key'));db.commit()
assert admin.get('/api/admin/sales'+q).json()['unreconciledOrders']==[{'orderNo':'ORD-pg-unknown','paymentStatus':'PARTIAL_CANCELED'}]
assert admin.get('/api/admin/sales/export.csv'+q).status_code==409
print('PASS: sales permissions, Korean date boundaries, completed refunds, pending exclusions, CSV and PG uncertainty')

assert anonymous.get('/api/chat/rooms').status_code==401
assert owner.get('/api/chat/rooms').json()[0]['id']=='all'
assert owner.post('/api/chat/rooms/direct',json={}).status_code==403
assert owner.post('/api/chat/rooms/direct',headers=headers(owner),json={'customerId':other_id}).status_code==403
response=owner.post('/api/chat/rooms/direct',headers=headers(owner),json={});assert response.status_code==200,response.text
room=response.json()['id'];path='/api/chat/rooms/'+room
assert admin.post('/api/chat/rooms/direct',headers=headers(admin),json={'customerId':uid}).json()['id']==room
assert len(owner.get('/api/chat/rooms').json())==2
assert all(r['id']!=room for r in other.get('/api/chat/rooms').json())
body={'content':'PRIVATE <script>alert(1)</script>','clientId':'first'}
sent=owner.post(path+'/messages',headers=headers(owner),json=body)
assert sent.status_code==200,sent.text
assert sent.json()['senderRole']=='customer' and sent.json()['isMine']
assert owner.post(path+'/messages',headers=headers(owner),json=body).json()['id']==sent.json()['id']
assert owner.post(path+'/messages',headers=headers(owner),json={**body,'content':'changed'}).status_code==409
assert owner.post(path+'/messages',headers=headers(owner),json={'content':'   ','clientId':'blank'}).status_code==400
assert owner.post(path+'/messages',headers=headers(owner),json={'content':'x'*2001,'clientId':'long'}).status_code==422
assert owner.post(path+'/messages',json=body).status_code==403
for suffix in ('/messages','/events'):
    assert other.get(path+suffix).status_code==404
    assert anonymous.get(path+suffix).status_code==401
assert other.post(path+'/messages',headers=headers(other),json=body).status_code==404
assert admin.get(path+'/messages').json()['messages'][0]['content']==body['content']
assert admin.get(path+'/messages').json()['messages'][0]['isMine'] is False
reply=admin.post(path+'/messages',headers=headers(admin),json={'content':'답변입니다','clientId':'admin-reply'})
assert reply.json()['senderRole']=='admin'
assert len(owner.get(path+'/messages?after='+str(sent.json()['id'])).json()['messages'])==1
assert owner.get(path+'/messages?after=-1').status_code==400
assert owner.get(path+'/messages?after=1&before=2').status_code==400
assert owner.get(path+'/messages').headers['cache-control']=='private, no-store'
with SessionLocal() as db:
    db.add_all([chat.ChatMessage(room_id='all',sender_id=uid,sender_name='고객',sender_role='customer',body='PUBLIC '+str(i),client_id='bulk-'+str(i)) for i in range(61)])
    db.commit()
public=other.get('/api/chat/rooms/all/messages').json()
assert len(public['messages'])==50 and public['hasOlder']
assert all('PRIVATE' not in m['content'] for m in public['messages'])
older=other.get('/api/chat/rooms/all/messages?before='+str(public['messages'][0]['id'])).json()
assert len(older['messages'])==11 and not older['hasOlder']
assert max(m['id'] for m in older['messages'])<min(m['id'] for m in public['messages'])

class StreamRequest:
    cookies=dict(owner.cookies)
    headers={}
    async def is_disconnected(self):return False

async def verify_stream():
    request=StreamRequest()
    with SessionLocal() as db:
        response=chat.events(room,request,after=sent.json()['id'],db=db)
        assert response.media_type=='text/event-stream'
        assert response.headers['x-accel-buffering']=='no'
    stream=response.body_iterator
    assert 'event: ready' in await anext(stream)
    batch=await anext(stream)
    assert 'event: messages' in batch and '답변입니다' in batch and 'PRIVATE' not in batch
    assert 'PUBLIC' not in batch
    with SessionLocal() as db:db.execute(delete(AuthSession).where(AuthSession.user_id==uid));db.commit()
    with patch.object(chat.asyncio,'sleep',new=AsyncMock()):
        assert 'event: access-denied' in await anext(stream)
    try:await anext(stream);raise AssertionError('Revoked stream stayed open')
    except StopAsyncIteration:pass
asyncio.run(verify_stream())
assert owner.get(path+'/messages').status_code==401
assert chat.stream_update(StreamRequest(),room,0) is None
print('PASS: private room ACL, CSRF, author identity, idempotent sends, history pagination, live SSE delivery and revoked sessions')
