"""Apply the mobile storefront after the final V21 features, using the same routes."""
from pathlib import Path
from shutil import copyfile

source = Path(__file__).resolve().parent / 'v21_mobile'
for name in ('mobile.css', 'mobile.js', 'shipping-addresses.css', 'shipping-addresses.js'):
    copyfile(source / name, Path('static/assets') / name)
copyfile(source / 'addresses.py', Path('app/addresses.py'))
copyfile(source / 'mobile-preview.html', Path('static/mobile-preview.html'))

pages = ('index', 'detail', 'checkout', 'login', 'mypage', 'guest-order',
         'return-request', 'board', 'chat', 'payment-success', 'payment-fail')
for name in pages:
    path = Path('static') / (name + '.html')
    text = path.read_text()
    text = text.replace('width=device-width,initial-scale=1',
                        'width=device-width,initial-scale=1,viewport-fit=cover')
    text = text.replace('</head>', '<meta name="theme-color" content="#2f7d4e">'
                        '<link rel="stylesheet" href="assets/mobile.css?v=21-mobile-1"></head>')
    text = text.replace('<body', f'<body data-shop-page="{name}"', 1)
    text = text.replace('</body>', '<script src="assets/mobile.js?v=21-mobile-1"></script></body>')
    path.write_text(text)

def replace(path, old, new):
    file = Path(path)
    text = file.read_text()
    if text.count(old) != 1:
        raise SystemExit(f'Expected one mobile target in {path}: {old[:80]}')
    file.write_text(text.replace(old, new))

replace('static/detail.html', '<div class="action"><button',
        '<div class="action"><div class="purchase-actions"><button')
replace('static/detail.html', '장바구니 담기</button><a', '장바구니 담기</button></div><a')
replace('static/checkout.html',
        '<button class="btn primary" id="payBtn" style="width:100%;margin-top:15px">주문하고 결제하기</button>',
        '<div class="checkout-paybar"><div class="mobile-pay-total"><small>최종 결제금액</small>'
        '<strong id="mobilePayTotal">0원</strong></div><button class="btn primary" id="payBtn" '
        'style="width:100%;margin-top:15px">주문하고 결제하기</button></div>')
replace('app/main.py', 'app.include_router(chat.router)',
        'app.include_router(chat.router)\nfrom . import addresses\napp.include_router(addresses.router)')
replace('app/main.py', '    guestPin: str = ""\nclass ConfirmIn',
        '    guestPin: str = ""\n    saveShippingAddress: bool = False\nclass ConfirmIn')
replace('app/main.py', '    o.inventory_deducted=True\n    db.commit()',
        '    o.inventory_deducted=True\n'
        '    saved_shipping = addresses.remember(db,u.id,data,strict=False) if u and data.saveShippingAddress else None\n'
        '    db.commit()')
replace('app/main.py', '    if guest_token: result["guestToken"]=guest_token',
        '    if u and data.saveShippingAddress: result["shippingAddressSaved"] = saved_shipping is not None\n'
        '    if guest_token: result["guestToken"]=guest_token')
replace('static/checkout.html', '</head>',
        '<link rel="stylesheet" href="assets/shipping-addresses.css?v=21-mobile-1"></head>')
replace('static/checkout.html', '<h2>배송지</h2><form',
        '<h2>배송지</h2>' + (source/'shipping-addresses.html').read_text() + '<form')
replace('static/checkout.html', '<input name="cashDepositor"></label></form>',
        '<input name="cashDepositor"></label></form><label class="save-shipping-option" '
        'id="saveShippingOption" hidden><input type="checkbox" id="saveShippingAddress" checked>'
        '<span>이 배송지를 주소록에 저장<small>주문이 접수되면 저장합니다. 다음 주문에서 선택할 수 있습니다. (최대 20개)</small></span></label>')
replace('static/checkout.html', '<script src="assets/shop-core.js"></script>',
        '<script src="assets/shop-core.js"></script><script src="assets/shipping-addresses.js?v=21-mobile-1"></script>')
replace('static/checkout.html', "if(me.authenticated){orderForm.customerName.value=me.name||'';",
        "if(me.authenticated){ShippingAddresses.mount({user:me,form:orderForm,onChange:recalc});orderForm.customerName.value=me.name||'';")
replace('static/checkout.html', "body:{items:itemsPayload,paymentMethod:method,",
        "body:{saveShippingAddress:!!me.authenticated&&document.getElementById('saveShippingAddress').checked,items:itemsPayload,paymentMethod:method,")
replace('static/checkout.html', 'if(o.guestToken){',
        'if(o.shippingAddressSaved===false){sessionStorage.setItem("shipping_address_notice",'
        '"주문은 접수되었지만 배송지를 저장하지 못했습니다. 저장 한도(20개)와 배송정보를 확인해 주세요.")}if(o.guestToken){')
print('V21 mobile storefront applied to 11 customer pages')
