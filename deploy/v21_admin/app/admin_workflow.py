"""Receipt-time refunds and compact administrator work counts."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, func, update
from sqlalchemy.orm import Session

from .db import get_db
from .models import Order, OrderCancelRequest, Product, ReturnRequest, Shipment
from .security import require_admin, require_csrf
from . import returns as returns_api

router = APIRouter()


@router.get('/api/admin/work-counts')
def admin_work_counts(request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    pending_cancel = select(OrderCancelRequest.order_id).where(OrderCancelRequest.status == 'REQUESTED')
    shipped = select(Shipment.order_id).where(
        (func.trim(Shipment.tracking_number) != '') | Shipment.status.in_(['SHIPPED', 'DELIVERED'])
    )
    orders = db.scalar(select(func.count()).select_from(Order).where(
        Order.order_status.in_(['ORDERED', 'PAID', 'PREPARING']),
        Order.payment_status.in_(['PENDING', 'AWAITING_DEPOSIT', 'WAITING_FOR_DEPOSIT', 'PAID']),
        Order.id.not_in(pending_cancel), Order.id.not_in(shipped),
    )) or 0
    counts = dict(db.execute(select(ReturnRequest.request_type, func.count()).where(
        ReturnRequest.status.in_(returns_api.ACTIVE_STATUSES)
    ).group_by(ReturnRequest.request_type)).all())
    cancellations = db.scalar(select(func.count()).select_from(OrderCancelRequest).where(
        OrderCancelRequest.status == 'REQUESTED'
    )) or 0
    return {'orders': orders, 'returns': counts.get('RETURN', 0),
            'exchanges': counts.get('EXCHANGE', 0), 'cancellations': cancellations,
            'updatedAt': returns_api.utcnow().isoformat()}


def receive_and_refund(request_no, data, request, db):
    require_csrf(request, db)
    require_admin(request, db)
    rr = returns_api._load_return(db, request_no)
    if not rr:
        raise HTTPException(404, '신청을 찾을 수 없습니다.')

    # Serialize receipts for an order on both PostgreSQL and SQLite before rereading
    # state. This prevents repeated clicks from restoring stock or refunding twice.
    db.execute(update(Order).where(Order.id == rr.order_id).values(order_status=Order.order_status))
    db.expire_all()
    rr = returns_api._load_return(db, request_no)
    if rr.status == 'REFUNDED' or (rr.request_type == 'EXCHANGE' and rr.status == 'RECEIVED'):
        db.commit()
        return returns_api._return_dict(rr)
    allowed = {'APPROVED', 'COLLECTING'}
    if rr.request_type == 'RETURN':
        allowed.add('RECEIVED')  # Also finish receipts saved before this upgrade.
        if rr.refund_status == 'MANUAL_PENDING':
            allowed.add('REFUNDING')
    if rr.status not in allowed:
        raise HTTPException(409, '승인·회수 또는 입고 후 환불 대기 건만 처리할 수 있습니다.')

    completed_at = returns_api.utcnow()
    if rr.request_type == 'RETURN':
        o = rr.order
        amount = rr.refund_amount
        already = returns_api._completed_refund_total(db, o.id, rr.id)
        if amount < 0 or amount > rr.item_amount:
            raise HTTPException(400, '승인된 환불금액을 확인해 주세요.')
        if already + amount > o.total_amount:
            raise HTTPException(409, '주문금액을 초과하여 환불할 수 없습니다.')
        manual = o.payment_method in {'CASH', 'VIRTUAL_ACCOUNT'} and amount > 0
        if manual:
            if not data or not data.manualRefundConfirmed:
                raise HTTPException(409, '실제 계좌 송금을 완료한 후 입고·환불 완료를 확인해 주세요.')
            if o.payment_method == 'CASH' and not rr.refund_bank_account:
                raise HTTPException(400, '현금 환불계좌 정보가 없습니다.')
            rr.refund_status = 'MANUAL_COMPLETED'
            rr.admin_note = ((rr.admin_note or '') + '\n입고 완료 시 관리자가 실제 송금 완료를 확인함').strip()
        elif amount > 0:
            if not o.payment_key:
                raise HTTPException(409, '결제 정보가 없어 자동 환불할 수 없습니다.')
            try:
                result = returns_api.payments.cancel(
                    o.payment_key, f'{rr.request_no} 반품 환불', amount=amount, idem=rr.request_no
                )
            except Exception as exc:
                db.rollback()
                raise HTTPException(502, f'환불 요청에 실패했습니다. 입고 완료를 다시 시도해 주세요. ({exc})')
            # Do not mark an asynchronously pending/failed cancellation as complete.
            # Response contract: https://docs.tosspayments.com/reference
            cancels = result.get('cancels') or []
            latest = cancels[-1] if cancels else {}
            if result.get('lastTransactionKey'):
                latest = next((c for c in cancels if c.get('transactionKey') == result['lastTransactionKey']), {})
            if (result.get('status') not in {'CANCELED', 'PARTIAL_CANCELED'} or
                    not latest or latest.get('cancelStatus') != 'DONE' or
                    ('cancelAmount' in latest and latest['cancelAmount'] != amount)):
                db.rollback()
                raise HTTPException(502, '결제사의 환불 완료를 확인하지 못했습니다. 확인 후 다시 시도해 주세요.')
            rr.refund_transaction_key = latest.get('transactionKey', '')
            rr.refund_status = 'COMPLETED'
        else:
            rr.refund_status = 'COMPLETED'  # Zero refund: no payment-provider request.
        rr.status = 'REFUNDED'
        rr.completed_at = completed_at
        total_refunded = already + amount
        returns_api._sync_reward_reversal(db, o, total_refunded, rr.request_no)
        o.payment_status = 'REFUNDED' if total_refunded >= o.total_amount else 'PARTIAL_REFUNDED'
        o.order_status = 'RETURNED' if total_refunded >= o.total_amount else 'PARTIAL_RETURN'
    else:
        rr.status = 'RECEIVED'
        rr.exchange_status = 'READY'

    if not rr.stock_restored:
        for item in rr.items:
            db.execute(update(Product).where(Product.id == item.product_id).values(stock=Product.stock + item.quantity))
        rr.stock_restored = True
    rr.pickup_status = 'RECEIVED'
    rr.received_at = rr.received_at or completed_at
    db.commit()
    db.expire_all()
    return returns_api._return_dict(returns_api._load_return(db, request_no))
