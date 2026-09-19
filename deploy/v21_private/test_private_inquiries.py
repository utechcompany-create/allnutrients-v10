"""Private question access checks, using only a temporary local database."""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
temp = tempfile.TemporaryDirectory(prefix='private-inquiry-test-')
os.environ.update(DATABASE_URL='sqlite:///'+str(Path(temp.name)/'local.db'), APP_ENV='development',
                  SESSION_COOKIE_SECURE='false', ADMIN_EMAIL='private-admin@example.test',
                  ADMIN_PASSWORD='LocalAdmin!234')

# Simulate an existing installation before the new metadata table is registered.
from app.db import Base, engine, SessionLocal
from app.models import BoardPost, Inquiry
Base.metadata.create_all(engine)
with SessionLocal() as db:
    db.add(BoardPost(id='legacy-board', author='기존 고객', category='일반문의', title='기존 공개글',
                     content='보존할 기존 내용', status='답변대기', messages_json='[]'))
    db.add(Inquiry(id='legacy-inquiry', product_id='P1001', product_name='기존 상품', author='기존 고객',
                   title='기존 상품 문의', content='보존할 기존 상품 문의', status='답변대기', messages_json='[]'))
    db.commit()

import app.main as m
from app.communications import CommunicationPrivacy
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select

m.seed()
m.seed()  # Repeated startup must preserve public data and private schema.
assert 'communication_privacy' in inspect(engine).get_table_names()
admin, owner, other, anonymous = (TestClient(m.app) for _ in range(4))
assert admin.post('/api/auth/login', json={'email':'private-admin@example.test','password':'LocalAdmin!234'}).status_code == 200
for client, name in ((owner,'비밀 작성자'),(other,'다른 회원')):
    assert client.post('/api/auth/register', json={'email':('owner' if client is owner else 'other')+'@example.test','password':'LocalMember!234','name':name}).status_code == 200
headers = lambda client: {'x-csrf-token':client.cookies.get('allnutrients_csrf')}

def listing(client, kind):
    r = client.get('/api/board' if kind == 'board' else '/api/inquiries?productId=P1001')
    assert r.status_code == 200, r.text
    assert r.headers['cache-control'] == 'private, no-store' and r.headers['vary'] == 'Cookie'
    return {row['id']:row for row in r.json()}

private_ids = {}
for kind in ('board','inquiry'):
    endpoint = '/api/board' if kind == 'board' else '/api/inquiries'
    base = {'category':'배송문의'} if kind == 'board' else {'productId':'P1001'}
    body = {**base,'title':'SECRET_TITLE_'+kind,'content':'SECRET_BODY_'+kind,'isPrivate':True}
    assert anonymous.post(endpoint,json=body).status_code == 401
    assert owner.post(endpoint,json=body).status_code == 403
    r = owner.post(endpoint,headers=headers(owner),json=body)
    assert r.status_code == 200, r.text
    item_id = r.json()['id']; private_ids[kind] = item_id
    assert r.json()['isPrivate'] is True
    assert owner.post(endpoint+'/'+item_id+'/followup',headers=headers(owner),json={'content':'SECRET_FOLLOW_'+kind}).status_code == 200
    reply = '/api/admin/communications/'+kind+'/'+item_id+'/reply'
    assert other.post(reply,headers=headers(other),json={'content':'ATTACK'}).status_code == 403
    assert admin.post(reply,headers=headers(admin),json={'content':'SECRET_REPLY_'+kind}).status_code == 200
    for client in (owner,admin):
        row = listing(client,kind)[item_id]
        assert row['title'] == body['title'] and row['content'] == body['content']
        assert row['canRead'] and row['canFollowup'] and row['isPrivate']
        assert row['messages'][-1]['content'] == 'SECRET_REPLY_'+kind
    for client in (other,anonymous):
        row = listing(client,kind)[item_id]
        assert row['title'] == '비밀글입니다.' and row['content'] == '' and row['author'] == '비공개'
        assert row['messages'] == [] and row['canRead'] is False and row['canFollowup'] is False
        assert 'SECRET_' not in str(row)
    assert other.post(endpoint+'/'+item_id+'/followup',headers=headers(other),json={'content':'ATTACK'}).status_code == 403
    assert anonymous.post(endpoint+'/'+item_id+'/followup',json={'content':'ATTACK'}).status_code == 401
    assert all(message['content'] != 'ATTACK' for message in listing(owner,kind)[item_id]['messages'])

    # Old clients can omit the flag; checkbox-off requests remain public.
    for extra in ({},{'isPrivate':False}):
        res = owner.post(endpoint,headers=headers(owner),json={**base,'title':'공개 문의','content':'공개 내용',**extra})
        assert res.status_code == 200, res.text
        public_id = res.json()['id']
        row = listing(anonymous,kind)[public_id]
        assert row['isPrivate'] is False and row['canRead'] is True and row['content'] == '공개 내용'
        assert other.post(endpoint+'/'+public_id+'/followup',headers=headers(other),json={'content':'공개 댓글'}).status_code == 200
    legacy = listing(anonymous,kind)['legacy-'+kind]
    assert legacy['isPrivate'] is False and legacy['content'].startswith('보존할 기존')

# Admin communication list contains the private flag and full thread for replying.
assert anonymous.get('/api/admin/communications').status_code == 401
assert other.get('/api/admin/communications').status_code == 403
comms = admin.get('/api/admin/communications')
assert comms.headers['cache-control'] == 'private, no-store'
for kind,key in (('board','board'),('inquiry','inquiries')):
    row = next(x for x in comms.json()[key] if x['id'] == private_ids[kind])
    assert row['isPrivate'] and row['title'].startswith('SECRET_TITLE_') and row['messages']

# Permissions are recalculated after logout / account changes, not cached per post.
assert owner.post('/api/auth/logout',headers=headers(owner)).status_code == 200
assert listing(owner,'board')[private_ids['board']]['canRead'] is False
assert owner.post('/api/auth/login',json={'email':'owner@example.test','password':'LocalMember!234'}).status_code == 200
assert listing(owner,'inquiry')[private_ids['inquiry']]['canRead'] is True

# Creating visibility and question content is one transaction; a failure cannot
# accidentally leave the question public. Failed privacy reads fail closed.
with patch('app.communications.save_privacy',side_effect=RuntimeError('synthetic failure')):
    client=TestClient(m.app,raise_server_exceptions=False);client.cookies.update(owner.cookies)
    assert client.post('/api/board',headers=headers(owner),json={'category':'일반문의','title':'MUST_NOT_PERSIST','content':'private','isPrivate':True}).status_code == 500
assert not any(row['title']=='MUST_NOT_PERSIST' for row in listing(admin,'board').values())
with patch('app.communications.privacy_flags',side_effect=RuntimeError('synthetic failure')):
    assert TestClient(m.app,raise_server_exceptions=False).get('/api/board').status_code == 500
with SessionLocal() as db:
    assert len(db.scalars(select(CommunicationPrivacy)).all()) == 2

for path in ('/board.html','/detail.html'):
    html=anonymous.get(path).text
    assert 'type="checkbox" name="isPrivate"' in html and 'assets/private-inquiries.js' in html
assert '🔒 비밀글' in admin.get('/admin.html').text
engine.dispose()
temp.cleanup()
print('PASS: private board/product questions, owner/admin/other/guest permissions, hidden titles/content/replies, followup protection, logout, cache headers, atomic writes, legacy data and additive startup')
