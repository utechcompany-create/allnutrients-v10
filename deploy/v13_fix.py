from pathlib import Path


def replace_once(path, old, new):
    p = Path(path)
    s = p.read_text()
    if old not in s:
        raise SystemExit(f'missing patch target: {path}: {old[:100]!r}')
    p.write_text(s.replace(old, new, 1))

s = Path('app/main.py').read_text()
if 'return_fee=0; exchange_fee=0' not in s:
    replace_once('app/main.py', 'options=[]; shipping_type="DEFAULT"; shipping_fee=0',
                 'options=[]; shipping_type="DEFAULT"; shipping_fee=0; return_fee=0; exchange_fee=0')
s = Path('app/main.py').read_text()
if 'rp=db.get(ProductReturnPolicy,p.id)' not in s:
    replace_once('app/main.py',
                 '        if ss: shipping_type=ss.shipping_type or "DEFAULT"; shipping_fee=max(0,int(ss.shipping_fee or 0))\n',
                 '        if ss: shipping_type=ss.shipping_type or "DEFAULT"; shipping_fee=max(0,int(ss.shipping_fee or 0))\n'
                 '        rp=db.get(ProductReturnPolicy,p.id)\n'
                 '        if rp: return_fee=max(0,int(rp.return_fee or 0)); exchange_fee=max(0,int(rp.exchange_fee or 0))\n')
s = Path('app/main.py').read_text()
if '"returnFee":return_fee,"exchangeFee":exchange_fee' not in s:
    replace_once('app/main.py',
                 '"options":options,"shippingType":shipping_type,"shippingFee":shipping_fee}',
                 '"options":options,"shippingType":shipping_type,"shippingFee":shipping_fee,"returnFee":return_fee,"exchangeFee":exchange_fee}')

s = Path('static/assets/admin-v11.js').read_text()
if 'id="productReturnFee"' not in s:
    old = '''const shipWrap=document.createElement('div');shipWrap.className='full';shipWrap.innerHTML=`<div style="font-weight:800;margin-bottom:8px">상품 배송비 설정</div><div class="grid2"><label>배송비 유형<select name="shippingType" id="productShippingType"><option value="DEFAULT">기본 배송비 적용</option><option value="FREE">무료배송</option><option value="FIXED">개별 배송비</option></select></label><label>개별 배송비<input type="number" name="shippingFee" id="productShippingFee" min="0" value="0"><span class="muted">개별 배송비 선택 시 적용됩니다.</span></label></div>`;productForm.insertBefore(shipWrap,descLabel);'''
    new = '''const shipWrap=document.createElement('div');shipWrap.className='full';shipWrap.innerHTML=`<div style="font-weight:800;margin-bottom:8px">상품 배송비 설정</div><div class="grid2"><label>배송비 유형<select name="shippingType" id="productShippingType"><option value="DEFAULT">기본 배송비 적용</option><option value="FREE">무료배송</option><option value="FIXED">개별 배송비</option></select></label><label>개별 배송비<input type="number" name="shippingFee" id="productShippingFee" min="0" value="0"><span class="muted">개별 배송비 선택 시 적용됩니다.</span></label></div><div style="font-weight:800;margin:16px 0 8px">반품·교환 배송비</div><div class="grid2"><label>반품 배송비<input type="number" name="returnFee" id="productReturnFee" min="0" value="6000"><span class="muted">고객 귀책 반품 시 환불금에서 자동 차감</span></label><label>교환 배송비<input type="number" name="exchangeFee" id="productExchangeFee" min="0" value="6000"><span class="muted">고객 귀책 교환 시 고객 부담금으로 자동 산정</span></label></div>`;productForm.insertBefore(shipWrap,descLabel);'''
    replace_once('static/assets/admin-v11.js', old, new)

for rej in [Path('app/main.py.rej'), Path('static/assets/admin-v11.js.rej')]:
    if rej.exists():
        rej.unlink()
