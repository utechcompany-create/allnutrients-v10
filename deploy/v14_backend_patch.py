from pathlib import Path

def rep(path, old, new):
    p=Path(path); s=p.read_text()
    if old not in s: raise SystemExit(f'missing {path}: {old[:100]!r}')
    p.write_text(s.replace(old,new,1))

# models
rep('app/models.py','class ReturnReasonPolicy(Base):\n','''class ProductPackingPolicy(Base):
    __tablename__ = "product_packing_policies"
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    bundle_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

class ReturnReasonPolicy(Base):
''')
rep('app/models.py','class Coupon(Base):\n','''class OrderShippingBreakdown(Base):
    __tablename__ = "order_shipping_breakdowns"
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), primary_key=True)
    bundled_fee: Mapped[int] = mapped_column(Integer, default=0)
    separate_fee: Mapped[int] = mapped_column(Integer, default=0)
    region_surcharge: Mapped[int] = mapped_column(Integer, default=0)
    package_count: Mapped[int] = mapped_column(Integer, default=0)
    region_type: Mapped[str] = mapped_column(String(20), default="MAINLAND")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Coupon(Base):
''')
# imports/version
rep('app/main.py','ProductShippingSetting, ProductReturnPolicy, ReturnReasonPolicy, OrderAdjustment, Coupon','ProductShippingSetting, ProductReturnPolicy, ProductPackingPolicy, ReturnReasonPolicy, OrderAdjustment, OrderShippingBreakdown, Coupon')
rep('app/returns.py','ProductReturnPolicy, ReturnReasonPolicy, ReturnFeeDecision','ProductReturnPolicy, ProductPackingPolicy, ReturnReasonPolicy, ReturnFeeDecision')
rep('app/main.py','version="13.0"','version="14.0"')
rep('app/main.py','return {"ok":True,"version":"13.0"}','return {"ok":True,"version":"14.0"}')
remote='울릉군,백령면,대청면,소청도,연평면,흑산면,홍도,가거도,거문도,추자면,욕지면,사량면,한산면,비금면,도초면,하의면,신의면,장산면,암태면,자은면,팔금면,안좌면'
rep('app/main.py','{"shippingFee":3000,"freeShippingThreshold":50000}','{"shippingFee":3000,"freeShippingThreshold":50000,"jejuExtraFee":3000,"remoteExtraFee":4000,"remoteAreaKeywords":"'+remote+'"}')
rep('app/main.py','commerce={"shippingFee":3000,"freeShippingThreshold":50000}','commerce={"shippingFee":3000,"freeShippingThreshold":50000,"jejuExtraFee":3000,"remoteExtraFee":4000,"remoteAreaKeywords":"'+remote+'"}')
rep('app/main.py','data={"shippingFee":3000,"freeShippingThreshold":50000}','data={"shippingFee":3000,"freeShippingThreshold":50000,"jejuExtraFee":3000,"remoteExtraFee":4000,"remoteAreaKeywords":"'+remote+'"}')
# product fields
rep('app/main.py','options=[]; shipping_type="DEFAULT"; shipping_fee=0; return_fee=0; exchange_fee=0','options=[]; shipping_type="DEFAULT"; shipping_fee=0; return_fee=0; exchange_fee=0; bundle_allowed=True')
rep('app/main.py','''        if ss: shipping_type=ss.shipping_type or "DEFAULT"; shipping_fee=max(0,int(ss.shipping_fee or 0))\n''','''        if ss: shipping_type=ss.shipping_type or "DEFAULT"; shipping_fee=max(0,int(ss.shipping_fee or 0))
        rp=db.get(ProductReturnPolicy,p.id)
        if rp: return_fee=max(0,int(rp.return_fee or 0)); exchange_fee=max(0,int(rp.exchange_fee or 0))
        pp=db.get(ProductPackingPolicy,p.id)
        if pp is not None: bundle_allowed=bool(pp.bundle_allowed)
''')
rep('app/main.py','"shippingType":shipping_type,"shippingFee":shipping_fee,"returnFee":return_fee,"exchangeFee":exchange_fee}','"shippingType":shipping_type,"shippingFee":shipping_fee,"returnFee":return_fee,"exchangeFee":exchange_fee,"bundleAllowed":bundle_allowed}')
rep('app/main.py','    exchangeFee:int=Field(default=0,ge=0,le=1000000)\n','    exchangeFee:int=Field(default=0,ge=0,le=1000000)\n    bundleAllowed:bool=True\n')
rep('app/main.py','''class CommerceIn(BaseModel):
    shippingFee:int=Field(ge=0,le=1000000)
    freeShippingThreshold:int=Field(ge=0,le=100000000)
''','''class CommerceIn(BaseModel):
    shippingFee:int=Field(ge=0,le=1000000)
    freeShippingThreshold:int=Field(ge=0,le=100000000)
    jejuExtraFee:int=Field(default=3000,ge=0,le=1000000)
    remoteExtraFee:int=Field(default=4000,ge=0,le=1000000)
    remoteAreaKeywords:str=""
''')
# order dict breakdown
rep('app/main.py','adj=None; return_fee_map={}','$SHIPPING_BREAKDOWN_INIT$')
rep('app/main.py','$SHIPPING_BREAKDOWN_INIT$','adj=None; return_fee_map={}; shipping_breakdown=None')
rep('app/main.py','''            if a: adj={"subtotal":a.subtotal,"shippingFee":a.shipping_fee,"couponDiscount":a.coupon_discount,"pointDiscount":a.point_discount,"couponId":a.coupon_id,"couponName":a.coupon_name}\n''','''            if a: adj={"subtotal":a.subtotal,"shippingFee":a.shipping_fee,"couponDiscount":a.coupon_discount,"pointDiscount":a.point_discount,"couponId":a.coupon_id,"couponName":a.coupon_name}
            sb=_db.get(OrderShippingBreakdown,o.id)
            if sb: shipping_breakdown={"bundledFee":sb.bundled_fee,"separateFee":sb.separate_fee,"regionSurcharge":sb.region_surcharge,"packageCount":sb.package_count,"regionType":sb.region_type}
''')
rep('app/main.py','except: adj=None; reward=0; return_fee_map={}\n','except: adj=None; reward=0; return_fee_map={}; shipping_breakdown=None\n')
rep('app/main.py','"totalAmount":o.total_amount,"adjustment":adj,','"totalAmount":o.total_amount,"adjustment":adj,"shippingBreakdown":shipping_breakdown,')
# shipping calc
old='''def product_shipping(db,pid):
 r=db.get(ProductShippingSetting,pid)
 if not r:return "DEFAULT",0
 k=(r.shipping_type or "DEFAULT").upper();return (k if k in {"DEFAULT","FREE","FIXED"} else "DEFAULT",max(0,int(r.shipping_fee or 0)))
def calculate_shipping(db,items,subtotal,commerce):
 fixed=0;default=False;seen=set()
 for p,*_ in items:
  if p.id in seen:continue
  seen.add(p.id);k,f=product_shipping(db,p.id)
  if k=="FIXED":fixed+=f
  elif k=="DEFAULT":default=True
 base=int(commerce.get("shippingFee",0) or 0) if default and subtotal<int(commerce.get("freeShippingThreshold",0) or 0) else 0
 return max(0,fixed+base)
'''
new='''def product_shipping(db:Session,product_id:str):
    row=db.get(ProductShippingSetting,product_id)
    if not row:return "DEFAULT",0
    kind=(row.shipping_type or "DEFAULT").upper()
    return (kind if kind in {"DEFAULT","FREE","FIXED"} else "DEFAULT",max(0,int(row.shipping_fee or 0)))

def product_bundle_allowed(db:Session,product_id:str):
    row=db.get(ProductPackingPolicy,product_id)
    return True if row is None else bool(row.bundle_allowed)

def delivery_region(postcode:str,address1:str,commerce:dict):
    post="".join(ch for ch in str(postcode or "") if ch.isdigit());addr=str(address1 or "").strip()
    if "제주" in addr or post.startswith("63"): return "JEJU",max(0,int(commerce.get("jejuExtraFee",3000) or 0))
    keys=[x.strip() for x in str(commerce.get("remoteAreaKeywords","") or "").replace("\\n",",").split(",") if x.strip()]
    if any(k in addr for k in keys): return "REMOTE",max(0,int(commerce.get("remoteExtraFee",4000) or 0))
    return "MAINLAND",0

def calculate_shipping(db:Session,items,subtotal:int,commerce:dict,postcode:str="",address1:str=""):
    default_fee=max(0,int(commerce.get("shippingFee",0) or 0));threshold=max(0,int(commerce.get("freeShippingThreshold",0) or 0));bundled=[];separate=0;packages=0;has_bundle=False
    for p,qty,*_rest in items:
        kind,fee=product_shipping(db,p.id);bundle=product_bundle_allowed(db,p.id);unit=0 if kind=="FREE" else (fee if kind=="FIXED" else default_fee)
        if bundle:
            has_bundle=True;bundled.append(0 if kind=="FREE" else (fee if kind=="FIXED" else (0 if subtotal>=threshold else default_fee)))
        else:
            separate+=unit*int(qty);packages+=int(qty)
    bundled_fee=max(bundled or [0]) if has_bundle else 0
    if has_bundle:packages+=1
    region_type,region_unit=delivery_region(postcode,address1,commerce);region_fee=region_unit*packages
    return {"total":max(0,bundled_fee+separate+region_fee),"bundledFee":bundled_fee,"separateFee":separate,"regionSurcharge":region_fee,"packageCount":packages,"regionType":region_type}
'''
rep('app/main.py',old,new)
rep('app/main.py','shipping=calculate_shipping(db,items,subtotal,commerce)','shipping_calc=calculate_shipping(db,items,subtotal,commerce,data.postcode,data.address1)\n    shipping=shipping_calc["total"]')
rep('app/main.py','''    db.add(OrderAdjustment(order_id=o.id,subtotal=subtotal,shipping_fee=shipping,coupon_discount=coupon_discount,point_discount=point_discount,coupon_id=(uc.coupon_id if uc else ""),coupon_name=coupon_name))\n''','''    db.add(OrderAdjustment(order_id=o.id,subtotal=subtotal,shipping_fee=shipping,coupon_discount=coupon_discount,point_discount=point_discount,coupon_id=(uc.coupon_id if uc else ""),coupon_name=coupon_name))
    db.add(OrderShippingBreakdown(order_id=o.id,bundled_fee=shipping_calc["bundledFee"],separate_fee=shipping_calc["separateFee"],region_surcharge=shipping_calc["regionSurcharge"],package_count=shipping_calc["packageCount"],region_type=shipping_calc["regionType"]))
''')
# product save
rep('app/main.py','db.add(ProductReturnPolicy(product_id=p.id,return_fee=data.returnFee,exchange_fee=data.exchangeFee))','db.add(ProductReturnPolicy(product_id=p.id,return_fee=data.returnFee,exchange_fee=data.exchangeFee))\n    db.add(ProductPackingPolicy(product_id=p.id,bundle_allowed=data.bundleAllowed))')
rep('app/main.py','''    rp.return_fee=data.returnFee;rp.exchange_fee=data.exchangeFee
    db.query(ProductOption)''','''    rp.return_fee=data.returnFee;rp.exchange_fee=data.exchangeFee
    pp=db.get(ProductPackingPolicy,p.id)
    if not pp:pp=ProductPackingPolicy(product_id=p.id);db.add(pp)
    pp.bundle_allowed=data.bundleAllowed
    db.query(ProductOption)''')
# returns fee
rep('app/returns.py','''def _policy_fee(db: Session, normalized, typ: str, responsibility: str):
    if responsibility != "CUSTOMER": return 0
    fees=[]
    for oi, qty, line in normalized:
        rp=db.get(ProductReturnPolicy,oi.product_id)
        if rp: fees.append(max(0,int(rp.return_fee if typ=="RETURN" else rp.exchange_fee or 0)))
    return max(fees or [0])
''','''def _policy_fee(db: Session, normalized, typ: str, responsibility: str):
    if responsibility != "CUSTOMER": return 0
    bundled=[];separate=0
    for oi, qty, line in normalized:
        rp=db.get(ProductReturnPolicy,oi.product_id);fee=max(0,int((rp.return_fee if typ=="RETURN" else rp.exchange_fee) or 0)) if rp else 0
        pp=db.get(ProductPackingPolicy,oi.product_id);bundle=True if pp is None else bool(pp.bundle_allowed)
        if bundle:bundled.append(fee)
        else:separate+=fee*int(qty)
    return max(bundled or [0])+separate
''')