"""Synthetic local data and mocked payments only; no production mutations."""
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from sqlalchemy import select
import test_return_request as regression
import test_v21 as f
from app.models import Order, Product, ReturnRequest

admin, member, m, AH, MH = f.admin, f.member, f.m, f.AH, f.MH


def counts():
    r = admin.get('/api/admin/work-counts')
    assert r.status_code == 200, r.text
    return {k: r.json()[k] for k in ('orders', 'returns', 'exchanges', 'cancellations')}


def record(no):
    return next(x for x in admin.get('/api/admin/returns').json() if x['requestNo'] == no)


def stock():
    with m.SessionLocal() as db:
        return db.get(Product, f.product['id']).stock


def approved(tag, method='CASH'):
    order = f.delivered_order(2, tag)
    r = f.request_return(order, 'DEFECT', 2)
    assert admin.post('/api/admin/returns/'+r['requestNo']+'/review', headers=AH, json={'approved': True}).status_code == 200
    with m.SessionLocal() as db:
        o = db.scalar(select(Order).where(Order.order_no == order['orderNo']))
        o.payment_method = method
        o.payment_key = 'local-payment' if method == 'CARD' else ''
        db.commit()
    return r


assert f.TestClient(m.app).get('/api/admin/work-counts').status_code == 401
assert member.get('/api/admin/work-counts').status_code == 403
baseline = counts()
r = approved('RECEIPT-MANUAL')
no = r['requestNo']; url = '/api/admin/returns/'+no+'/receive'
before = stock()
assert counts()['returns'] == baseline['returns'] + 1
assert member.post(url, headers=MH, json={'manualRefundConfirmed': True}).status_code == 403
assert admin.post(url, json={'manualRefundConfirmed': True}).status_code == 403
assert admin.post(url, headers=AH).status_code == 409
assert stock() == before and record(no)['receivedAt'] is None
done = admin.post(url, headers=AH, json={'manualRefundConfirmed': True})
assert done.status_code == 200, done.text
done = done.json()
assert done['status'] == 'REFUNDED' and done['refundStatus'] == 'MANUAL_COMPLETED'
assert done['completedAt'] == done['receivedAt'] and done['completedAt']
assert stock() == before + 2 and counts()['returns'] == baseline['returns']
again = admin.post(url, headers=AH).json()
assert again['completedAt'] == done['completedAt'] and stock() == before + 2
assert member.get('/api/returns/my', params={'orderNo': r['orderNo']}).json()[0]['status'] == 'REFUNDED'

# PG failure and pending responses must leave both inventory and completion intact.
r = approved('RECEIPT-CARD', 'CARD'); no = r['requestNo']; url = '/api/admin/returns/'+no+'/receive'
before = stock()
with patch('app.returns.payments.cancel', side_effect=RuntimeError('local simulated failure')):
    assert admin.post(url, headers=AH).status_code == 502
assert record(no)['status'] == 'APPROVED' and record(no)['receivedAt'] is None and stock() == before
with patch('app.returns.payments.cancel', return_value={'status': 'PARTIAL_CANCELED', 'cancels': [{'cancelStatus': 'PENDING'}]}):
    assert admin.post(url, headers=AH).status_code == 502
assert stock() == before and record(no)['completedAt'] is None
with patch('app.returns.payments.cancel', return_value={'status': 'PARTIAL_CANCELED', 'cancels': [{'cancelStatus': 'DONE', 'transactionKey': 'local-only'}]}) as pg:
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: admin.post(url, headers=AH), range(2)))
    assert all(x.status_code == 200 for x in results), [x.text for x in results]
    pg.assert_called_once()
    assert pg.call_args.kwargs['idem'] == no
assert stock() == before + 2 and record(no)['status'] == 'REFUNDED'

# Missing payment keys and refund caps cannot accidentally restore inventory.
r = approved('RECEIPT-MISSING', 'CARD'); no = r['requestNo']; url = '/api/admin/returns/'+no+'/receive'
with m.SessionLocal() as db:
    o = db.scalar(select(Order).where(Order.order_no == r['orderNo'])); o.payment_key = ''; db.commit()
before = stock()
assert admin.post(url, headers=AH).status_code == 409
assert stock() == before and record(no)['completedAt'] is None
with m.SessionLocal() as db:
    o = db.scalar(select(Order).where(Order.order_no == r['orderNo'])); o.total_amount = 1; db.commit()
assert admin.post(url, headers=AH).status_code == 409
assert stock() == before

# No PG request is made for a zero-value refund.
r = approved('RECEIPT-ZERO', 'CARD'); no = r['requestNo']
with m.SessionLocal() as db:
    rr = db.scalar(select(ReturnRequest).where(ReturnRequest.request_no == no)); rr.refund_amount = 0; db.commit()
with patch('app.returns.payments.cancel') as pg:
    assert admin.post('/api/admin/returns/'+no+'/receive', headers=AH).json()['status'] == 'REFUNDED'
    pg.assert_not_called()

# Legacy pending manual refunds can be completed through the same receipt button.
r = approved('RECEIPT-LEGACY', 'VIRTUAL_ACCOUNT'); no = r['requestNo']
with m.SessionLocal() as db:
    rr = db.scalar(select(ReturnRequest).where(ReturnRequest.request_no == no))
    rr.status = 'REFUNDING'; rr.refund_status = 'MANUAL_PENDING'; rr.stock_restored = True
    rr.received_at = m.utcnow(); db.commit()
before = stock()
res = admin.post('/api/admin/returns/'+no+'/receive', headers=AH, json={'manualRefundConfirmed': True})
assert res.status_code == 200 and res.json()['refundStatus'] == 'MANUAL_COMPLETED'
assert stock() == before

# Exchange receipts restore stock and stay on the counter until delivery completion.
baseline = counts()
order = f.delivered_order(2, 'EXCHANGE-RECEIPT')
res = member.post('/api/returns', headers=MH, json={'orderNo': order['orderNo'], 'requestType': 'EXCHANGE', 'reasonCode': 'DEFECT', 'items': [{'orderItemId': order['items'][0]['orderItemId'], 'qty': 1}]})
assert res.status_code == 200, res.text
no = res.json()['requestNo']; prefix = '/api/admin/returns/'+no
assert counts()['exchanges'] == baseline['exchanges'] + 1
assert admin.post(prefix+'/review', headers=AH, json={'approved': True}).status_code == 200
with patch('app.returns.payments.cancel') as pg:
    res = admin.post(prefix+'/receive', headers=AH)
    assert res.status_code == 200 and res.json()['status'] == 'RECEIVED' and res.json()['completedAt'] is None
    pg.assert_not_called()
assert counts()['exchanges'] == baseline['exchanges'] + 1
assert admin.post(prefix+'/exchange-shipment', headers=AH, json={'carrier': 'CJ', 'trackingNumber': 'LOCAL-ONLY'}).status_code == 200
assert admin.post(prefix+'/complete', headers=AH, json={}).status_code == 200
assert counts()['exchanges'] == baseline['exchanges']

# Actual checkout/cancel/review operations move counts between menus, not cumulative totals.
baseline = counts()
order = member.post('/api/orders', headers=MH, json={
    'items': [{'productId': f.product['id'], 'optionId': f.option['id'], 'qty': 1}],
    'paymentMethod': 'CASH', 'customerName': '카운터 테스트', 'customerEmail': f.email,
    'customerPhone': '01012345678', 'postcode': '06236', 'address1': '서울 강남구', 'address2': '테스트',
    'deliveryMemo': '', 'cashDepositor': '테스트', 'couponId': '', 'pointsToUse': 0,
})
assert order.status_code == 200, order.text
no = order.json()['orderNo']
assert counts()['orders'] == baseline['orders'] + 1
assert member.post('/api/orders/'+no+'/cancel-request', headers=MH, json={'reason': 'CHANGE_MIND'}).status_code == 200
assert counts()['orders'] == baseline['orders'] and counts()['cancellations'] == baseline['cancellations'] + 1
assert admin.post('/api/admin/orders/'+no+'/cancel-review', headers=AH, json={'action': 'REJECT', 'adminNote': 'local test'}).status_code == 200
assert counts()['orders'] == baseline['orders'] + 1 and counts()['cancellations'] == baseline['cancellations']
assert member.post('/api/orders/'+no+'/cancel-request', headers=MH, json={'reason': 'CHANGE_MIND'}).status_code == 200
assert admin.post('/api/admin/orders/'+no+'/cancel-review', headers=AH, json={'action': 'APPROVE'}).status_code == 200
assert counts()['orders'] == baseline['orders'] and counts()['cancellations'] == baseline['cancellations']

for page in ('/admin.html', '/returns-admin.html'):
    html = admin.get(page).text
    for key in ('orders', 'returns', 'exchanges', 'cancellations'):
        assert 'data-work-count="'+key+'"' in html
    assert 'assets/admin-workflow.js' in html
print('PASS: receipt-time manual/card refunds, timestamp, concurrent idempotency, rollback, zero/legacy refunds, exchange flow, authorization, and live work counts')
