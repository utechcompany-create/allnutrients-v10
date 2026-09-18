"""Run only against the local test database; never calls a payment provider."""
import test_mypage_returns as previous
import test_v21 as fixture
from app.models import Order, Shipment
from sqlalchemy import select

admin, member, m, AH, MH = fixture.admin, fixture.member, fixture.m, fixture.AH, fixture.MH

def tracking_only(tag):
    order=fixture.delivered_order(4,tag)
    with m.SessionLocal() as db:
        saved=db.scalar(select(Order).where(Order.order_no==order['orderNo']))
        saved.order_status='PREPARING'
        shipment=db.scalar(select(Shipment).where(Shipment.order_id==saved.id))
        shipment.status='PREPARING'
        db.commit()
    return member.get('/api/orders/'+order['orderNo']).json()

first=tracking_only('REQUEST-RETURN')
record=fixture.request_return(first,'CHANGE_MIND',2)
assert record['returnShippingFee']==2000
second=tracking_only('REQUEST-EXCHANGE')
body={'orderNo':second['orderNo'],'requestType':'EXCHANGE','reasonCode':'DEFECT','items':[{'orderItemId':second['items'][0]['orderItemId'],'qty':1}]}
result=member.post('/api/returns',headers=MH,json=body)
assert result.status_code==200,result.text
assert result.json()['requestType']=='EXCHANGE'
assert result.json()['returnShippingFee']==0
assert member.get('/api/returns/my',params={'orderNo':second['orderNo']}).json()[0]['requestNo']==result.json()['requestNo']

# Remaining quantity is enforced by the server, even if a client changes the form.
too_many={**body,'orderNo':first['orderNo'],'items':[{'orderItemId':first['items'][0]['orderItemId'],'qty':3}]}
assert member.post('/api/returns',headers=MH,json=too_many).status_code==409
assert member.get('/assets/return-request.js').status_code==200
page=member.get('/return-request.html').text
assert 'id="requestBox" hidden' not in page
assert 'id="requestHistoryList"' in page
print('PASS: tracking-only orders accept returns and exchanges; duplicate quantities remain blocked')
