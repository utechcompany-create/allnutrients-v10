"""Apply the admin workflow after V21 and its customer UI overlay."""
from pathlib import Path
from shutil import copyfile


def replace(path, old, new):
    p = Path(path)
    text = p.read_text()
    if text.count(old) != 1:
        raise SystemExit(f'Expected one admin patch target in {path}: {old[:80]}')
    p.write_text(text.replace(old, new, 1))


source = Path(__file__).resolve().parent / 'v21_admin'
for relative in ('app/admin_workflow.py', 'static/assets/admin-workflow.js', 'static/assets/admin-workflow.css', 'static/assets/admin-labels.js'):
    destination = Path(relative)
    destination.parent.mkdir(parents=True, exist_ok=True)
    copyfile(source / relative, destination)

replace('app/main.py', 'app.include_router(returns.router)',
        'app.include_router(returns.router)\nfrom . import admin_workflow\napp.include_router(admin_workflow.router)')
replace('app/returns.py', 'class ManualRefundIn(BaseModel):',
        'class ReceiveIn(BaseModel):\n    manualRefundConfirmed: bool = False\n\n\nclass ManualRefundIn(BaseModel):')
returns = Path('app/returns.py')
text = returns.read_text()
start = text.index('def admin_receive(')
end = text.index('\n\ndef _sync_reward_reversal', start)
text = text[:start] + '''def admin_receive(request_no: str, request: Request, data: ReceiveIn | None = None, db: Session = Depends(get_db)):
    from .admin_workflow import receive_and_refund
    return receive_and_refund(request_no, data, request, db)
''' + text[end:]
returns.write_text(text)


def count(key):
    return f'<span class="work-count" data-work-count="{key}" aria-live="polite">—</span>'


orders_link = '<button class="work-menu" data-view="orders" data-order-scope="all" data-label="주문·배송"><span>주문·배송</span>' + count('orders') + '</button>'
cancel_link = '<button class="work-menu work-submenu" data-view="orders" data-order-scope="cancel" data-label="취소 신청"><span>취소 신청</span>' + count('cancellations') + '</button>'
return_links = '<a href="returns-admin.html">반품·교환 관리</a><a class="work-menu work-submenu" href="returns-admin.html?type=RETURN&active=1"><span>반품</span>' + count('returns') + '</a><a class="work-menu work-submenu" href="returns-admin.html?type=EXCHANGE&active=1"><span>교환</span>' + count('exchanges') + '</a>'
replace('static/admin.html', '<button data-view="orders">주문·배송</button><a href="returns-admin.html">반품·교환 관리</a>', orders_link + cancel_link + return_links)
replace('static/admin.html', 'title.textContent=b.textContent',
        "title.textContent=b.dataset.label||b.textContent;if(b.dataset.view==='orders'){document.getElementById('orderScope').value=b.dataset.orderScope||'all';renderOrders();loadAll().catch(e=>toast(e.message))}")
replace('static/admin.html', '<div id="orderList"></div>',
        '<label class="order-scope">주문 보기<select id="orderScope" onchange="renderOrders()"><option value="all">전체 주문</option><option value="pending">미발송 주문</option><option value="cancel">취소 승인 대기</option></select></label><div id="orderList"></div>')
replace('static/admin.html', 'function renderOrders(){orderList.innerHTML=orders.length?orders.map(',
        "function renderOrders(){const scope=document.getElementById('orderScope').value;const shown=orders.filter(o=>scope==='cancel'?o.cancelRequest?.status==='REQUESTED':scope==='pending'?(['ORDERED','PAID','PREPARING'].includes(o.orderStatus)&&['PENDING','AWAITING_DEPOSIT','WAITING_FOR_DEPOSIT','PAID'].includes(o.paymentStatus)&&o.cancelRequest?.status!=='REQUESTED'&&!String(o.shipment?.trackingNumber||'').trim()&&!['SHIPPED','DELIVERED'].includes(o.shipment?.status)):true);orderList.innerHTML=shown.length?shown.map(")
replace('static/admin.html', 'renderProducts();renderOrders();renderUsers();renderComms()}',
        'renderProducts();renderOrders();renderUsers();renderComms();window.AdminWorkCounts?.refresh()}')
replace('static/admin.html', "toast('주문상태를 변경했습니다.')", "await loadAll();toast('주문상태를 변경했습니다.')")
replace('static/admin.html', 'auth().then(loadAll).catch(()=>{});', """auth().then(loadAll).then(()=>{const q=new URLSearchParams(location.search);if(q.get('view')==='orders'){const scope=q.get('scope')==='cancel'?'cancel':'all';document.querySelector(`[data-view="orders"][data-order-scope="${scope}"]`).click()}}).catch(()=>{});""")

path = 'static/returns-admin.html'
replace(path, '접수 → 승인 → 회수 → 입고 → 환불 또는 교환 재배송 순서로 처리합니다.',
        '반품은 입고 완료 시 승인된 금액으로 환불을 완료합니다. 현금·가상계좌는 실제 송금을 확인해 주세요. 교환은 입고 후 재배송합니다.')
replace(path, '<select id="statusFilter">', '<select id="statusFilter" aria-label="처리 상태"><option value="ACTIVE">처리 중인 건</option>')
replace(path, '<select id="typeFilter">', '<select id="typeFilter" aria-label="신청 유형">')
replace(path, "(!s||r.status===s)", "(!s||(s==='ACTIVE'?!['REFUNDED','COMPLETED','REJECTED','CANCELED'].includes(r.status):r.status===s))")
replace(path, 'render();renderReasons()}', 'render();renderReasons();window.AdminWorkCounts?.refresh()}')
replace(path, "typeFilter.onchange=render;", "const initialFilters=new URLSearchParams(location.search);typeFilter.value=['RETURN','EXCHANGE'].includes(initialFilters.get('type'))?initialFilters.get('type'):'';statusFilter.value=initialFilters.get('active')==='1'?'ACTIVE':'';typeFilter.onchange=render;")
replace(path, "onclick=\"receive('${r.requestNo}')\">입고완료", "onclick=\"receive('${r.requestNo}')\">입고 완료")
replace(path, "onclick=\"refundReq('${r.requestNo}')\">환불 처리", "onclick=\"receive('${r.requestNo}')\">입고·환불 완료")
replace(path, "onclick=\"manualRefund('${r.requestNo}')\">수동 환불완료", "onclick=\"receive('${r.requestNo}')\">입고·환불 완료")
replace(path, 'value="${r.returnShippingFee||0}"', 'value="${r.returnShippingFee||0}" ${r.status!==\'REQUESTED\'?\'readonly\':\'\'}')
replace(path, 'value="${r.refundAmount||0}"', 'value="${r.refundAmount||0}" ${r.status!==\'REQUESTED\'?\'readonly\':\'\'}')
html = Path(path).read_text()
start = html.index('async function receive(no)')
end = html.index('async function refundReq(no)', start)
html = html[:start] + '''const receiving=new Set();
async function receive(no){
  if(receiving.has(no))return;
  const r=rows.find(x=>x.requestNo===no);if(!r)return;
  const isReturn=r.requestType==='RETURN';
  const manual=isReturn&&['CASH','VIRTUAL_ACCOUNT'].includes(r.paymentMethod)&&r.refundAmount>0;
  let message='상품의 실제 입고를 확인했습니까? 재고가 복구됩니다.';
  if(isReturn)message+='\\n승인된 환불금액: '+money(r.refundAmount)+' (배송비 차감 '+money(r.returnShippingFee)+')';
  if(manual)message+='\\n해당 금액의 실제 계좌 송금을 완료한 경우에만 확인해 주세요. 확인 시 입고와 환불이 함께 완료됩니다.';
  else if(isReturn)message+='\\n입고 완료와 함께 결제 환불을 실행합니다.';
  if(!confirm(message))return;
  receiving.add(no);
  document.querySelectorAll('[data-receive-no]').forEach(b=>{if(b.dataset.receiveNo===no)b.disabled=true});
  try{
    await api('/api/admin/returns/'+encodeURIComponent(no)+'/receive',{method:'POST',body:{manualRefundConfirmed:manual}});
    await load();toastMsg(isReturn?'입고 및 환불 완료 처리했습니다.':'입고 완료 처리했습니다. 교환품을 재배송해 주세요.');
  }catch(e){toastMsg(e.message)}
  finally{receiving.delete(no);document.querySelectorAll('[data-receive-no]').forEach(b=>{if(b.dataset.receiveNo===no)b.disabled=false})}
}
''' + html[end:]
html = html.replace('onclick="receive(\'${r.requestNo}\')"', 'data-receive-no="${r.requestNo}" onclick="receive(\'${r.requestNo}\')"')
Path(path).write_text(html)

sidebar = '<aside class="side"><h2>올영양소 <small style="display:block;font-size:11px;color:#9caea2">ONLINE ADMIN</small></h2><nav><a href="admin.html">대시보드</a><a class="work-menu" href="admin.html?view=orders"><span>주문·배송</span>' + count('orders') + '</a><a class="work-menu work-submenu" href="admin.html?view=orders&scope=cancel"><span>취소 신청</span>' + count('cancellations') + '</a><a class="active" href="returns-admin.html">반품·교환 관리</a><a class="work-menu work-submenu" href="returns-admin.html?type=RETURN&active=1"><span>반품</span>' + count('returns') + '</a><a class="work-menu work-submenu" href="returns-admin.html?type=EXCHANGE&active=1"><span>교환</span>' + count('exchanges') + '</a><p class="work-help">미발송 주문과 처리 중인 신청 건수<br>30초마다 자동 갱신</p><a href="index.html" target="_blank">쇼핑몰 보기 ↗</a></nav></aside>'
replace(path, '<body>', '<body><div class="workflow-shell">' + sidebar + '<div class="workflow-body">')
replace(path, '<script src="assets/api.js"></script>', '</div></div><script src="assets/api.js"></script>')
replace('static/admin.html', '<button id="logout">', '<p class="work-help">미발송 주문과 처리 중인 신청 건수<br>30초마다 자동 갱신</p><button id="logout">')
for page in ('static/admin.html', path):
    replace(page, '</head>', '<link rel="stylesheet" href="assets/admin-workflow.css"></head>')
    replace(page, '</body>', '<script src="assets/admin-workflow.js"></script></body>')

replace('static/admin.html', '<script src="assets/api.js"></script>', '<script src="assets/api.js"></script><script src="assets/admin-labels.js"></script>')
replace('static/admin.html', '${esc(o.paymentStatus)}', '${esc(AdminLabels.paymentStatus(o.paymentStatus))}')
replace('static/admin.html', '${esc(o.paymentMethod)}', '${esc(AdminLabels.paymentMethod(o.paymentMethod))}')
replace('static/admin.html', '${esc(o.cancelRequest.status)}', '${esc(AdminLabels.cancellationStatus(o.cancelRequest.status))}')
replace('static/admin.html', "['ORDERED','PAID','PREPARING','SHIPPED','DELIVERED','CANCELED'].map(s=>`<option ${s===o.orderStatus?'selected':''}>${s}</option>`)", "AdminLabels.orderOptions(o.orderStatus).map(s=>`<option value=\"${esc(s)}\" ${s===o.orderStatus?'selected':''} ${AdminLabels.editableOrder(s)?'':'disabled'}>${esc(AdminLabels.orderStatus(s))}</option>`)")
replace('static/admin.html', "['PREPARING','SHIPPED','DELIVERED','RETURNED'].map(s=>`<option ${s===o.shipment?.status?'selected':''}>${s}</option>`)", "AdminLabels.shippingOptions(o.shipment?.status).map(s=>`<option value=\"${esc(s)}\" ${s===o.shipment?.status?'selected':''} ${AdminLabels.editableShipping(s)?'':'disabled'}>${esc(AdminLabels.shippingStatus(s))}</option>`)")
print('V21 receipt-time refunds, administrator counters and Korean order labels applied')
