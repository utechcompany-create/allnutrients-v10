"""Local-only member history checks, including the V21 refund policy regression."""
from unittest.mock import patch
import test_v21 as fixture
from app.models import Order
from sqlalchemy import select

m, admin, member, AH, MH = fixture.m, fixture.admin, fixture.member, fixture.AH, fixture.MH


def finish_return(record, automatic=False):
    no = record['requestNo']
    approved = admin.post(f'/api/admin/returns/{no}/review', headers=AH, json={'approved': True})
    assert approved.status_code == 200, approved.text
    assert approved.json()['receiptConfirmed'] is False
    assert approved.json()['refundCompleted'] is False
    if automatic:
        with m.SessionLocal() as db:
            order = db.scalar(select(Order).where(Order.order_no == record['orderNo']))
            order.payment_method = 'CARD'
            order.payment_key = 'local-test-payment'
            db.commit()
        with patch('app.returns.payments.cancel', return_value={'status': 'PARTIAL_CANCELED', 'cancels': [{'transactionKey': 'local-test-refund', 'cancelStatus': 'DONE'}]}) as cancel:
            result = admin.post(f'/api/admin/returns/{no}/receive', headers=AH)
            cancel.assert_called_once()
        assert result.status_code == 200, result.text
        assert result.json()['refundStatus'] == 'COMPLETED'
    else:
        result = admin.post(f'/api/admin/returns/{no}/receive', headers=AH, json={'manualRefundConfirmed': True})
        assert result.status_code == 200, result.text
        assert result.json()['refundStatus'] == 'MANUAL_COMPLETED'
    assert result.json()['completedAt']
    assert result.json()['receiptConfirmed'] is True and result.json()['refundCompleted'] is True
    assert result.json()['completedAt'] == result.json()['receivedAt']
    assert result.json()['status'] == 'REFUNDED'
    return result.json()


finish_return(fixture.partial)
finish_return(fixture.full)
finish_return(fixture.defect, automatic=True)
history = member.get('/api/returns/my')
assert history.status_code == 200
records = {r['requestNo']: r for r in history.json()}
for original in [fixture.partial, fixture.full, fixture.defect]:
    found = records[original['requestNo']]
    assert found['status'] == 'REFUNDED' and found['completedAt']
    assert found['refundAmount'] == original['refundAmount']
    assert found['returnShippingFee'] == original['returnShippingFee']
    assert found['items'] == original['items']
    assert found['reasonName'] == original['reasonName']
    filtered = member.get('/api/returns/my', params={'orderNo': original['orderNo']}).json()
    assert len(filtered) == 1 and filtered[0]['requestNo'] == original['requestNo']

# Completed records remain readable even if the order no longer accepts a return.
for original in [fixture.full, fixture.defect]:
    assert member.get('/api/orders/' + original['orderNo']).status_code == 200

other = fixture.TestClient(m.app)
assert other.post('/api/auth/register', json={'email': 'history-other@example.com', 'password': 'LocalTest!234', 'name': '다른 회원'}).status_code == 200
assert other.get('/api/returns/my').json() == []
assert other.get('/api/returns/my', params={'orderNo': fixture.partial['orderNo']}).json() == []
assert other.get('/api/orders/' + fixture.partial['orderNo']).status_code == 403
anonymous = fixture.TestClient(m.app)
assert anonymous.get('/api/returns/my').status_code == 401

for path in ['/mypage.html', '/assets/mypage-returns.js', '/assets/mypage-returns.css']:
    response = member.get(path)
    assert response.status_code == 200, path
print('PASS: completed full/partial returns, manual/card refunds, fee policy, owner-only history and static assets')
