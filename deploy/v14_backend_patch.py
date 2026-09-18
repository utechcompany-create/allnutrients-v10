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
rep('app/main.py','adj=None; return_fee_map={}','$REPLACE_MARKER$')
