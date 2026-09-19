"""Administrator sales report, grouped by Korean order date."""
import csv
import io
from datetime import date, datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from .db import get_db
from .models import Order, ReturnRequest
from .security import require_admin

router = APIRouter()
KST = timezone(timedelta(hours=9))
PAID = {'PAID', 'PARTIAL_REFUNDED', 'REFUNDED', 'REFUND_PENDING'}
PAYMENT_LABELS = {'PAID':'결제 완료','PARTIAL_REFUNDED':'부분 환불 완료','REFUNDED':'환불 완료',
                  'PARTIAL_CANCELED':'부분 결제 취소','REFUND_PENDING':'환불 대기'}
METHOD_LABELS = {'CASH':'무통장입금','CARD':'신용·체크카드','NAVERPAY':'네이버페이','KAKAOPAY':'카카오페이','VIRTUAL_ACCOUNT':'가상계좌'}


def period(start, end):
    today = datetime.now(KST).date()
    try:
        first = date.fromisoformat(start) if start else today.replace(day=1)
        last = date.fromisoformat(end) if end else today
    except ValueError:
        raise HTTPException(400, '조회 날짜를 확인해 주세요.')
    if first > last or (last-first).days > 365:
        raise HTTPException(400, '시작일 이후의 종료일을 선택해 주세요. 한 번에 최대 366일을 조회할 수 있습니다.')
    return first, last


def report(db, start, end):
    first, last = period(start, end)
    lower = datetime.combine(first, datetime.min.time(), KST).astimezone(timezone.utc)
    upper = datetime.combine(last+timedelta(days=1), datetime.min.time(), KST).astimezone(timezone.utc)
    orders = db.scalars(select(Order).where(Order.created_at >= lower, Order.created_at < upper,
        Order.payment_status.in_(PAID)).order_by(Order.created_at.desc(), Order.order_no)).all()
    # Legacy PG callbacks preserve status but not the verified canceled amount.
    # Never guess that amount or silently count those orders as full net sales.
    unresolved = db.scalars(select(Order).where(Order.created_at >= lower, Order.created_at < upper,
        (Order.payment_status == 'PARTIAL_CANCELED') |
        ((Order.payment_status == 'CANCELED') & (Order.payment_key != '')))).all()
    ids = [o.id for o in orders]
    refunds = dict(db.execute(select(ReturnRequest.order_id, func.sum(ReturnRequest.refund_amount)).where(
        ReturnRequest.order_id.in_(ids), ReturnRequest.request_type == 'RETURN',
        ReturnRequest.refund_status.in_(['COMPLETED','MANUAL_COMPLETED'])
    ).group_by(ReturnRequest.order_id)).all()) if ids else {}
    rows, days = [], {}
    for o in orders:
        created = o.created_at if o.created_at.tzinfo else o.created_at.replace(tzinfo=timezone.utc)
        day = created.astimezone(KST).date().isoformat()
        gross = int(o.total_amount)
        refunded = min(gross, int(refunds.get(o.id, 0)))
        if o.payment_status == 'REFUNDED':
            refunded = gross
        row = {'orderNo':o.order_no,'orderedAt':created.isoformat(),'date':day,'customerName':o.customer_name,
               'paymentMethod':o.payment_method,'paymentStatus':o.payment_status,
               'grossAmount':gross,'refundAmount':refunded,'netAmount':gross-refunded}
        rows.append(row)
        bucket = days.setdefault(day, {'date':day,'orderCount':0,'grossAmount':0,'refundAmount':0,'netAmount':0})
        bucket['orderCount'] += 1
        for key in ('grossAmount','refundAmount','netAmount'):
            bucket[key] += row[key]
    totals = {'orderCount':len(rows), **{key:sum(r[key] for r in rows) for key in ('grossAmount','refundAmount','netAmount')}}
    return {'start':first.isoformat(),'end':last.isoformat(),'totals':totals,
            'daily':[days[d] for d in sorted(days)],'orders':rows,
            'unreconciledOrders':[{'orderNo':o.order_no,'paymentStatus':o.payment_status} for o in unresolved],
            'updatedAt':datetime.now(timezone.utc).isoformat()}


@router.get('/api/admin/sales')
def sales_report(request: Request, response: Response, start: str = '', end: str = '', db: Session = Depends(get_db)):
    require_admin(request, db)
    response.headers['Cache-Control'] = 'private, no-store'
    return report(db, start, end)


def csv_cell(value):
    text = str(value)
    return "'"+text if text.lstrip().startswith(('=','+','-','@')) else text


@router.get('/api/admin/sales/export.csv')
def export_sales(request: Request, start: str = '', end: str = '', db: Session = Depends(get_db)):
    require_admin(request, db)
    data = report(db, start, end)
    if data['unreconciledOrders']:
        raise HTTPException(409,'PG 취소 금액 확인이 필요한 주문이 있습니다. 매출 관리 화면에서 주문번호를 확인해 주세요.')
    out = io.StringIO(newline='')
    writer = csv.writer(out)
    writer.writerow(['주문일(한국시간)','주문번호','주문자','결제수단','결제상태','결제 매출','완료 환불액','순매출'])
    for row in data['orders']:
        writer.writerow([row['date'],csv_cell(row['orderNo']),csv_cell(row['customerName']),
            csv_cell(METHOD_LABELS.get(row['paymentMethod'],row['paymentMethod'])),
            csv_cell(PAYMENT_LABELS.get(row['paymentStatus'],row['paymentStatus'])),
            row['grossAmount'],row['refundAmount'],row['netAmount']])
    return Response(out.getvalue().encode('utf-8-sig'), media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition':f'attachment; filename="sales_{data["start"]}_{data["end"]}.csv"',
                 'Cache-Control':'private, no-store'})
