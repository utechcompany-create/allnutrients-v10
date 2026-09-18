from pathlib import Path

def rep(path, old, new):
    p=Path(path); s=p.read_text()
    if old not in s:
        raise SystemExit(f'missing patch target: {path}: {old[:120]!r}')
    p.write_text(s.replace(old,new,1))

rep('app/main.py','version="19.0"','version="21.0"')
rep('app/main.py','return {"ok":True,"version":"20.0"}','return {"ok":True,"version":"21.0"}')

old='''def _policy_fee(db: Session, normalized, typ: str, responsibility: str, reason_code: str = "", reason_name: str = ""):
    # V16: 반품은 단순변심만 배송비 0원, 그 외 사유는 상품에 설정된 반품비를 적용한다.
    # 교환은 기존 귀책정책을 유지하여 고객 귀책일 때만 교환배송비를 부담한다.
    change_mind = (reason_code or "").upper()=="CHANGE_MIND" or (reason_name or "").replace(" ","")=="단순변심"
    if typ=="RETURN":
        if change_mind:return 0
    elif responsibility != "CUSTOMER":
        return 0
    from fractions import Fraction
    bundled=[];separate=0;load=Fraction(0,1);has_bundle=False
    for oi, qty, line in normalized:
        rp=db.get(ProductReturnPolicy,oi.product_id)
        fee=max(0,int((rp.return_fee if typ=="RETURN" else rp.exchange_fee) or 0)) if rp else 0
        option_id=getattr(oi,"option_id","") or ""
        op=db.get(ProductOption,option_id) if option_id else None
        if op and op.product_id==oi.product_id:
            bundle=bool(op.bundle_allowed); capacity=max(0,int(op.bundle_capacity or 0))
        else:
            pp=db.get(ProductPackingPolicy,oi.product_id); bundle=True if pp is None else bool(pp.bundle_allowed); capacity=0
        if bundle:
            has_bundle=True; bundled.append(fee)
            if capacity>0: load += Fraction(int(qty),capacity)
        else: separate += fee*int(qty)
    packages=max(1,(load.numerator+load.denominator-1)//load.denominator) if has_bundle and load else (1 if has_bundle else 0)
    return max(bundled or [0])*packages+separate
'''
new='''def _policy_fee(db: Session, o: Order, normalized, typ: str, responsibility: str, reason_code: str = "", reason_name: str = ""):
    # V21 return fee policy:
    # - RETURN: only change-of-mind deducts the product-configured return fee.
    # - Other return reasons deduct 0 so the selected merchandise amount is fully refunded.
    # - For a partial change-of-mind return that fits in exactly one calculated return package,
    #   deduct only 50% of the configured return fee.
    # - EXCHANGE keeps the existing responsibility policy.
    change_mind = (reason_code or "").upper()=="CHANGE_MIND" or (reason_name or "").replace(" ","")=="단순변심"
    if typ=="RETURN" and not change_mind:
        return 0
    if typ=="EXCHANGE" and responsibility != "CUSTOMER":
        return 0

    from fractions import Fraction
    bundled=[];separate=0;load=Fraction(0,1);has_bundle=False;separate_packages=0
    for oi, qty, line in normalized:
        rp=db.get(ProductReturnPolicy,oi.product_id)
        fee=max(0,int((rp.return_fee if typ=="RETURN" else rp.exchange_fee) or 0)) if rp else 0
        option_id=getattr(oi,"option_id","") or ""
        op=db.get(ProductOption,option_id) if option_id else None
        if op and op.product_id==oi.product_id:
            bundle=bool(op.bundle_allowed); capacity=max(0,int(op.bundle_capacity or 0))
        else:
            pp=db.get(ProductPackingPolicy,oi.product_id); bundle=True if pp is None else bool(pp.bundle_allowed); capacity=0
        if bundle:
            has_bundle=True; bundled.append(fee)
            if capacity>0:
                load += Fraction(int(qty),capacity)
        else:
            separate += fee*int(qty)
            separate_packages += int(qty)

    bundled_packages=max(1,(load.numerator+load.denominator-1)//load.denominator) if has_bundle and load else (1 if has_bundle else 0)
    packages=bundled_packages+separate_packages
    fee_total=max(bundled or [0])*bundled_packages+separate

    if typ=="RETURN" and change_mind:
        requested={int(oi.id):int(qty) for oi,qty,_ in normalized}
        partial=any(requested.get(int(oi.id),0) < int(oi.quantity) for oi in o.items)
        if partial and packages==1:
            return fee_total//2
    return fee_total
'''
rep('app/returns.py',old,new)
rep('app/returns.py','auto_fee=_policy_fee(db,normalized,typ,reason.responsibility,reason.code,reason.name)','auto_fee=_policy_fee(db,o,normalized,typ,reason.responsibility,reason.code,reason.name)')

old="""function pickedFee(key){const picked=[...document.querySelectorAll('.pick:checked')];let bundled=[],separate=0;for(const c of picked){const fee=Number(c.dataset[key]||0),bundle=c.dataset.bundle!=='false',qty=Number(document.querySelector(`.qty[data-id="${c.dataset.id}"]`)?.value||1);if(bundle)bundled.push(fee);else separate+=fee*qty}return Math.max(0,...bundled)+separate}function updateFeeNotice(){if(!order||!reasons.length)return;const r=reasons.find(x=>x.code===reasonCode.value);if(!r){feeNotice.textContent='사유를 선택해 주세요.';return}const typ=requestForm.requestType.value,changeMind=r.code==='CHANGE_MIND'||String(r.name||'').replace(/\s/g,'')==='단순변심';let fee=0;if(typ==='RETURN'){fee=changeMind?0:pickedFee('returnFee')}else if(r.responsibility==='CUSTOMER'){fee=pickedFee('exchangeFee')}const who=r.responsibility==='CUSTOMER'?'고객 귀책':r.responsibility==='SELLER'?'판매자 귀책':'배송비 면제';feeNotice.innerHTML=typ==='RETURN'?`<b>${esc(r.name)}</b> · ${changeMind?'단순변심 반품배송비는 <b>0원</b>입니다.':(fee?`예상 반품배송비 <b>${money(fee)}</b>가 환불금에서 자동 차감됩니다.`:'상품 설정 반품배송비가 0원입니다.')}`:`<b>${esc(who)}</b> · ${fee?`교환 배송비 고객 부담 <b>${money(fee)}</b>`:'교환 배송비 고객 부담 없음'}`;}
"""
new="""function pickedFee(key){const picked=[...document.querySelectorAll('.pick:checked')];let bundled=[],separate=0,bundleLoad=0,hasBundle=false,separatePackages=0;for(const c of picked){const fee=Number(c.dataset[key]||0),bundle=c.dataset.bundle!=='false',capacity=Math.max(0,Number(c.dataset.capacity||0)),qty=Number(document.querySelector(`.qty[data-id="${c.dataset.id}"]`)?.value||1);if(bundle){hasBundle=true;bundled.push(fee);if(capacity>0)bundleLoad+=qty/capacity}else{separate+=fee*qty;separatePackages+=qty}}const bundledPackages=hasBundle?Math.max(1,Math.ceil(bundleLoad-1e-12)):0;return {fee:Math.max(0,...bundled)*bundledPackages+separate,packages:bundledPackages+separatePackages}}function isPartialReturn(){const picked=[...document.querySelectorAll('.pick:checked')];if(!order||!picked.length)return false;const requested=new Map(picked.map(c=>[Number(c.dataset.id),Number(document.querySelector(`.qty[data-id="${c.dataset.id}"]`)?.value||0)]));return order.items.some(i=>(requested.get(Number(i.orderItemId))||0)<Number(i.qty||0))}function updateFeeNotice(){if(!order||!reasons.length)return;const r=reasons.find(x=>x.code===reasonCode.value);if(!r){feeNotice.textContent='사유를 선택해 주세요.';return}const typ=requestForm.requestType.value,changeMind=r.code==='CHANGE_MIND'||String(r.name||'').replace(/\s/g,'')==='단순변심';let fee=0,calc={fee:0,packages:0};if(typ==='RETURN'){if(changeMind){calc=pickedFee('returnFee');fee=calc.fee;if(isPartialReturn()&&calc.packages===1)fee=Math.floor(fee/2)}}else if(r.responsibility==='CUSTOMER'){calc=pickedFee('exchangeFee');fee=calc.fee}const who=r.responsibility==='CUSTOMER'?'고객 귀책':r.responsibility==='SELLER'?'판매자 귀책':'배송비 면제';feeNotice.innerHTML=typ==='RETURN'?`<b>${esc(r.name)}</b> · ${changeMind?(fee?`예상 반품배송비 <b>${money(fee)}</b>가 환불금에서 자동 차감됩니다.${isPartialReturn()&&calc.packages===1?' <span class="muted">부분반품 1박스 기준으로 설정 반품비의 50%를 적용합니다.</span>':''}`:'상품 설정 반품배송비가 0원입니다.'):'반품배송비 차감 없이 선택 상품금액을 <b>전액 환불</b>합니다.'}`:`<b>${esc(who)}</b> · ${fee?`교환 배송비 고객 부담 <b>${money(fee)}</b>`:'교환 배송비 고객 부담 없음'}`;}
"""
rep('static/return-request.html',old,new)
rep('static/return-request.html','data-bundle="${i.bundleAllowed!==false}"','data-bundle="${i.bundleAllowed!==false}" data-capacity="${Number(i.bundleCapacity||0)}"')
Path('V20_TO_V21_UPGRADE.md').write_text('''# V20 → V21

- 단순변심 반품에만 상품 등록의 반품배송비를 차감합니다.
- 그 외 반품 사유는 차감 없이 선택 상품금액을 전액 환불합니다.
- 부분 반품이면서 반품 물량이 계산상 1박스인 경우 설정 반품배송비의 50%만 차감합니다.
- 옵션별 합포장 가능 수량을 반품 박스 계산에도 적용합니다.
''')

# Apply the reviewed customer UI after all legacy source overlays and patches.
# These files only change customer pages; the refund policy and database stay intact.
from shutil import copyfile
ui_source = Path(__file__).resolve().parent / 'v21_ui'
for relative in (
    'static/mypage.html',
    'static/return-request.html',
    'static/assets/mypage-returns.js',
    'static/assets/mypage-returns.css',
    'static/assets/return-request.js',
):
    destination = Path(relative)
    destination.parent.mkdir(parents=True, exist_ok=True)
    copyfile(ui_source / relative, destination)
print('V21 customer return/exchange forms and refund history applied')
