"""Local-only regression for inconsistent legacy flags; never repairs money records."""
import test_v21 as f
from app.models import ReturnRequest
from app.returns import utcnow
from sqlalchemy import select

number = f.partial['requestNo']
for status, refund, receipt, expected in (
    ('REQUESTED', 'PENDING_REVIEW', False, False),
    ('APPROVED', 'COMPLETED', False, False),
    ('COLLECTING', 'MANUAL_COMPLETED', False, False),
    ('REFUNDED', 'COMPLETED', False, False),
    ('APPROVED', 'COMPLETED', True, False),
    ('RECEIVED', 'MANUAL_PENDING', True, False),
    ('REJECTED', 'COMPLETED', True, False),
    ('REFUNDED', 'COMPLETED', True, True),
    ('REFUNDED', 'MANUAL_COMPLETED', True, True),
    ('COMPLETED', 'COMPLETED', True, True),
):
    with f.m.SessionLocal() as db:
        row = db.scalar(select(ReturnRequest).where(ReturnRequest.request_no == number))
        row.status, row.refund_status = status, refund
        row.received_at = utcnow() if receipt else None
        db.commit()
    row = next(x for x in f.member.get('/api/returns/my').json() if x['requestNo'] == number)
    assert row['receiptConfirmed'] is receipt
    assert row['refundCompleted'] is expected
    assert row['refundStatus'] == refund and row['status'] == status
    admin_row = next(x for x in f.admin.get('/api/admin/returns').json() if x['requestNo'] == number)
    assert admin_row['refundCompleted'] is expected
    with f.m.SessionLocal() as db:
        stored = db.scalar(select(ReturnRequest).where(ReturnRequest.request_no == number))
        assert stored.status == status and stored.refund_status == refund

print('PASS: customer/admin completion agrees; missing receipts and mismatched flags never complete; read-only serialization preserves stored payment records')
