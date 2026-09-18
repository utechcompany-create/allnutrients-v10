from pathlib import Path

def rep(path,old,new):
 p=Path(path);s=p.read_text();assert old in s,(path,old[:50]);p.write_text(s.replace(old,new,1))
rep('app/main.py','''    db.add(p);db.flush()
    for idx,o in enumerate(data.options):''','''    db.add(p);db.flush()
    kind=data.shippingType.upper() if data.shippingType.upper() in {"DEFAULT","FREE","FIXED"} else "DEFAULT"
    db.add(ProductShippingSetting(product_id=p.id,shipping_type=kind,shipping_fee=(data.shippingFee if kind=="FIXED" else 0)))
    for idx,o in enumerate(data.options):''')
rep('app/main.py','''    p.detail_title=data.detailTitle;p.detail_text=data.detailText;p.detail_images_json=json.dumps(data.detailImages,ensure_ascii=False)
    db.query(ProductOption).filter(ProductOption.product_id==p.id).delete(synchronize_session=False)''','''    p.detail_title=data.detailTitle;p.detail_text=data.detailText;p.detail_images_json=json.dumps(data.detailImages,ensure_ascii=False)
    kind=data.shippingType.upper() if data.shippingType.upper() in {"DEFAULT","FREE","FIXED"} else "DEFAULT";ss=db.get(ProductShippingSetting,p.id)
    if not ss:ss=ProductShippingSetting(product_id=p.id);db.add(ss)
    ss.shipping_type=kind;ss.shipping_fee=(data.shippingFee if kind=="FIXED" else 0)
    db.query(ProductOption).filter(ProductOption.product_id==p.id).delete(synchronize_session=False)''')
rep('app/main.py','''    if o.payment_status!="PAID":
        o.payment_status="PAID";o.order_status="PAID"
    db.commit();return {"ok":True}
''','''    if o.payment_status!="PAID":
        o.payment_status="PAID";o.order_status="PAID";award_order_points(db,o)
    db.commit();return {"ok":True,"rewardPoints":int(db.scalar(select(func.coalesce(func.sum(PointLedger.amount),0)).where(PointLedger.order_id==o.id,PointLedger.amount>0,PointLedger.reason.like("구매 적립%"))) or 0)}
''')
rep('app/main.py','''def point_balance(db:Session,user_id:str):
    return int(db.scalar(select(func.coalesce(func.sum(PointLedger.amount),0)).where(PointLedger.user_id==user_id)) or 0)
''','''def point_balance(db:Session,user_id:str):
    return max(0,int(db.scalar(select(func.coalesce(func.sum(PointLedger.amount),0)).where(PointLedger.user_id==user_id)) or 0))
''')
rep('app/returns.py','from .models import Order, OrderItem, Product, ReturnRequest, ReturnItem','from .models import Order, OrderItem, Product, ReturnRequest, ReturnItem, PointLedger')
rep('app/returns.py','def _completed_refund_total(db: Session, order_id: str, exclude_request_id: str = ""):
','''def _sync_reward_reversal(db,o,total_refunded,ref):
 if not o or (o.user_id or "").startswith("guest_") or int(o.total_amount or 0)<=0:return
 earned=int(db.scalar(select(func.coalesce(func.sum(PointLedger.amount),0)).where(PointLedger.order_id==o.id,PointLedger.amount>0,PointLedger.reason.like("구매 적립%"))) or 0)
 if earned<=0:return
 rev=-int(db.scalar(select(func.coalesce(func.sum(PointLedger.amount),0)).where(PointLedger.order_id==o.id,PointLedger.amount<0,PointLedger.reason.like("구매 적립 회수%"))) or 0)
 target=min(earned,earned*min(int(total_refunded or 0),int(o.total_amount or 0))//max(1,int(o.total_amount or 0)));diff=max(0,target-rev)
 if diff:db.add(PointLedger(id=new_id("pt"),user_id=o.user_id,amount=-diff,reason=f"구매 적립 회수 {ref}",order_id=o.id))

def _completed_refund_total(db: Session, order_id: str, exclude_request_id: str = ""):
''')
rep('app/returns.py','''    total_refunded = already + amount
    o.payment_status = "REFUNDED"''','''    total_refunded = already + amount
    _sync_reward_reversal(db,o,total_refunded,rr.request_no)
    o.payment_status = "REFUNDED"''')
rep('app/returns.py','''    total_refunded=already+rr.refund_amount; o.payment_status="REFUNDED"''','''    total_refunded=already+rr.refund_amount; _sync_reward_reversal(db,o,total_refunded,rr.request_no); o.payment_status="REFUNDED"''')