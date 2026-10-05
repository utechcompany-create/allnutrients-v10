"""Storefront entry and purchase usability fixes, applied after V21 overlays."""
from pathlib import Path
from shutil import copyfile

source = Path(__file__).resolve().parent / 'v21_storefront'
version = '21-usability-1'
for name in ('login-access.js', 'checkout-readiness.js', 'storefront-usability.css'):
    copyfile(source / name, Path('static/assets') / name)

def replace(path, old, new):
    file = Path(path)
    text = file.read_text()
    if text.count(old) != 1:
        raise SystemExit(f'Expected one storefront target in {path}: {old[:90]}')
    file.write_text(text.replace(old, new))

replace('static/index.html', 'id="accountLink" href="login.html">로그인</a>',
        'id="accountLink" href="login.html">로그인/회원가입</a>')
replace('static/assets/account-nav.js', "el.textContent='로그인'", "el.textContent='로그인/회원가입'")
replace('static/index.html', 'src="assets/account-nav.js"', f'src="assets/account-nav.js?v={version}"')
replace('static/assets/mobile.js', '>로그인 · 회원가입</a>', '>로그인/회원가입</a>')
for path in Path('static').glob('*.html'):
    text = path.read_text()
    if 'assets/mobile.js?v=21-mobile-1' in text:
        path.write_text(text.replace('assets/mobile.js?v=21-mobile-1', f'assets/mobile.js?v={version}'))
for name in ('index', 'login', 'checkout', 'detail'):
    replace(f'static/{name}.html', '</head>',
            f'<link rel="stylesheet" href="assets/storefront-usability.css?v={version}"></head>')

replace('static/login.html', '<title>로그인 | 올영양소</title>', '<title>로그인/회원가입 | 올영양소</title>')
replace('static/login.html', '<h1 class="page-title">회원 로그인</h1><p class="sub">주문과 결제, 배송 조회를 위해 로그인해 주세요.</p>',
        '<h1 class="page-title">로그인/회원가입</h1><p class="sub">기존 회원은 로그인하고, 처음 방문하셨다면 회원가입을 진행해 주세요.</p>'
        '<nav class="auth-entry-actions" aria-label="로그인 및 회원가입 바로가기">'
        '<a class="btn ghost" href="#loginSection" data-auth-jump>로그인하기</a>'
        '<a class="btn primary" href="#registerSection" data-auth-jump>회원가입하기</a></nav>')
replace('static/login.html', '<section class="card"><h2>로그인</h2>',
        '<section class="card auth-section" id="loginSection"><h2>로그인</h2>')
replace('static/login.html', '<section class="card"><h2>회원가입</h2>',
        '<section class="card auth-section" id="registerSection"><h2>회원가입</h2>')
replace('static/login.html', 'minlength="8" required></label>',
        'minlength="8" required aria-describedby="registerPasswordHint"></label>'
        '<p class="full auth-hint" id="registerPasswordHint">비밀번호는 8자 이상 입력해 주세요.</p>')
for label in ('로그인', '회원가입'):
    replace('static/login.html', f'<button class="btn primary full">{label}</button>',
            '<p class="form-error full" role="alert" tabindex="-1" hidden></p>'
            f'<button type="submit" class="btn primary full">{label}</button>')
path = Path('static/login.html')
text = path.read_text()
start = text.index('<script>\nconst t=')
end = text.index('</script>', start) + len('</script>')
path.write_text(text[:start] + f'<script src="assets/login-access.js?v={version}"></script>' + text[end:])

# Match the server's coupon calculation: merchandise subtotal, excluding shipping.
replace('static/checkout.html', 'function couponAmount(cp,base)', 'function couponAmount(cp,base,total=base)')
replace('static/checkout.html', 'return Math.min(d,base)', 'return Math.min(d,total)')
replace('static/checkout.html', 'couponAmount(cp,calc.subtotal+calc.shipping)', 'couponAmount(cp,calc.subtotal,calc.subtotal+calc.shipping)')
replace('static/checkout.html', '<span>배송비</span>', '<span>배송비 (추가비용 포함)</span>')
replace('static/checkout.html', '<span>제주/도서산간 추가비용</span>', '<span>배송비 중 제주/도서산간</span>')
replace('static/checkout.html', '<div class="checkout-grid">',
        '<div id="checkoutMemberEntry" class="notice checkout-member-entry" hidden>'
        '<p>회원으로 주문하면 쿠폰·포인트와 저장된 배송지를 이용할 수 있습니다.</p>'
        '<a class="btn ghost" href="login.html?next=checkout.html">로그인/회원가입</a></div><div class="checkout-grid">')
replace('static/checkout.html', 'id="payBtn" style=', 'id="payBtn" disabled style=')
replace('static/checkout.html', '<p class="muted" id="pgHint"></p>',
        '<p class="muted" id="pgHint" role="status">결제수단을 확인하고 있습니다.</p>'
        '<p id="checkoutError" class="form-error" role="alert" hidden></p>')
replace('static/checkout.html', '<script src="assets/shipping-addresses.js?v=21-mobile-1"></script>',
        '<script src="assets/shipping-addresses.js?v=21-mobile-1"></script>'
        f'<script src="assets/checkout-readiness.js?v={version}"></script>')
replace('static/checkout.html', 'else{guestNotice.hidden=false;ensureGuestPinFields();',
        'else{guestNotice.hidden=false;checkoutMemberEntry.hidden=false;ensureGuestPinFields();')
replace('static/checkout.html', "pgHint.textContent=config.tossEnabled?'카드·네이버페이·카카오페이는 PG 결제창으로 연결됩니다.':'현재 PG 키가 없어 카드/간편결제는 사용할 수 없습니다. 현금 결제를 이용하세요.';recalc()",
        'CheckoutReadiness.configure(config);recalc()')
replace('static/checkout.html', "return toast('주문 PIN이 일치하지 않습니다.');try{const o=",
        "return toast('주문 PIN이 일치하지 않습니다.');if(!CheckoutReadiness.start(method))return;try{const o=")
replace('static/checkout.html', 'await requestToss(o)}catch(err){toast(err.message)}}',
        'await requestToss(o)}catch(err){CheckoutReadiness.error(err.message);CheckoutReadiness.finish()}}')
replace('static/checkout.html', 'payBtn.onclick=placeOrder;init().catch(e=>toast(e.message));',
        "payBtn.onclick=placeOrder;init().catch(e=>{CheckoutReadiness.error('주문 정보를 불러오지 못했습니다. 새로고침 후 다시 시도해 주세요.');payBtn.disabled=true;payBtn.textContent='주문 정보 확인 필요'});")

# Only move to checkout once adding a purchasable integer quantity succeeds.
replace('static/detail.html', "function qty(){return Math.max(1,Math.min(Number(p.stock||1),Number(document.getElementById('qty').value||1)))}",
        "function qty(){return Number(document.getElementById('qty').value)}")
start = "function putCart(replace=false){"
path = Path('static/detail.html')
text = path.read_text()
a = text.index(start)
b = text.index('let inquiryLoadId=', a)
text = text[:a] + """function putCart(replace=false){
 if(!p||p.status!=='판매중'||Number(p.stock)<=0){toast('현재 구매할 수 없는 상품입니다.');return false}
 if((p.options||[]).filter(o=>o.active!==false).length&&!selectedOption){toast('옵션을 선택해 주세요.');return false}
 const q=qty();if(!Number.isSafeInteger(q)||q<1||q>Number(p.stock)){toast('수량을 재고 범위 내의 정수로 입력해 주세요.');document.getElementById('qty').focus();return false}
 const cart=replace?{}:C.read(C.KEYS.cart,{}),k=key();
 const existing=Object.entries(cart).filter(([key])=>key.split('::')[0]===p.id).reduce((total,[,count])=>total+Number(count||0),0);
 if(existing+q>Number(p.stock)){toast('재고 수량을 초과할 수 없습니다.');return false}
 cart[k]=replace?q:Number(cart[k]||0)+q;
 try{C.save(C.KEYS.cart,cart);toast('장바구니에 담았습니다.');return true}catch(err){toast(err.message);return false}
}
function buyNow(){if(putCart(true))location.href='checkout.html'}
""" + text[b:]
path.write_text(text)
replace('static/detail.html', 'onclick="buyNow()">즉시 구매</button>',
        'onclick="buyNow()" ${p.status!==\'판매중\'||Number(p.stock)<=0?\'disabled\':\'\'}>${p.status===\'판매중\'&&Number(p.stock)>0?\'즉시 구매\':\'구매 불가\'}</button>')
replace('static/detail.html', 'onclick="putCart(false)">장바구니 담기</button>',
        'onclick="putCart(false)" ${p.status!==\'판매중\'||Number(p.stock)<=0?\'disabled\':\'\'}>장바구니 담기</button>')
print('V21 storefront signup entry, checkout readiness and purchase validation applied')
