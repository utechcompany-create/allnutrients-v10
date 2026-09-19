"""Layer administrator notifications onto the final V21 build."""
from pathlib import Path
from shutil import copyfile

source = Path(__file__).resolve().parent / 'v21_events'
copyfile(source/'admin_events.py', Path('app/admin_events.py'))
for name in ('admin-events.js','admin-events.css'):
    copyfile(source/name, Path('static/assets')/name)

def replace(path, old, new, count=1):
    file=Path(path);text=file.read_text()
    if text.count(old)!=count:
        raise SystemExit(f'Expected {count} event target(s) in {path}: {old[:100]}')
    file.write_text(text.replace(old,new))

replace('app/main.py','app.include_router(addresses.router)',
        'app.include_router(addresses.router)\nfrom . import admin_events\napp.include_router(admin_events.router)')
replace('app/main.py','        db.commit()\n\n@app.on_event("startup")',
        '        admin_events.backfill(db)\n        db.commit()\n\n@app.on_event("startup")')

# Record activity in the same transaction as its message/post, without message text.
replace('app/chat.py','    db.add(message)\n    try:\n        db.commit()',
        "    db.add(message)\n    try:\n        db.flush()\n        if viewer.role != 'admin':\n"
        "            from .admin_events import record\n"
        "            record(db,'groupChat' if db.get(ChatRoom,room_id).kind == 'GROUP' else 'directChat',room_id,message.id)\n"
        '        db.commit()')
replace('app/communications.py','from sqlalchemy import Boolean, String, select',
        'from sqlalchemy import Boolean, String, select, update')
replace('app/communications.py','    save_privacy(db, \'board\', row, data.isPrivate)',
        "    save_privacy(db, 'board', row, data.isPrivate)\n    if user.role != 'admin':\n        from .admin_events import record\n        record(db,'board',row.id,1)")
replace('app/communications.py','    save_privacy(db, \'inquiry\', row, data.isPrivate)',
        "    save_privacy(db, 'inquiry', row, data.isPrivate)\n    if user.role != 'admin':\n        from .admin_events import record\n        record(db,'inquiry',row.id,1)")
replace('app/communications.py',"    try:\n        messages = json.loads(row.messages_json or '[]')",
        "    model = type(row)\n    db.execute(update(model).where(model.id == row.id).values(status=model.status))\n    db.refresh(row)\n    try:\n        messages = json.loads(row.messages_json or '[]')",count=2)
replace('app/communications.py',"messages.append({'role': 'customer', 'author': user.name,",
        "messages.append({'role': 'seller' if user.role == 'admin' else 'customer', 'author': user.name,")
replace('app/communications.py',"    row.status = '답변대기'\n    db.commit()",
        "    row.status = '답변대기'\n    if user.role != 'admin':\n        from .admin_events import record\n        record(db,kind,row.id,len(messages)+1)\n    db.commit()")
replace('app/communications.py',"        out[key] = [serialize(row, kind, admin, flags.get(row.id, False)) for row in rows]",
        "        from .admin_events import thread_metadata\n        metadata = thread_metadata(db,admin.id,kind)\n        out[key] = [{**serialize(row,kind,admin,flags.get(row.id,False)),**metadata.get(row.id,{'unreadCount':0,'notificationThrough':0})} for row in rows]")

def badge(key):
    return f'<span class="work-count" data-work-count="{key}" aria-live="polite">—</span>'

replace('static/admin.html','<button type="button" id="chatMenuToggle" aria-expanded="true" aria-controls="chatSubnav">실시간 대화방 ▾</button>',
        '<button type="button" class="work-menu" id="chatMenuToggle" aria-expanded="true" aria-controls="chatSubnav"><span>실시간 대화방 ▾</span>'+badge('liveChat')+'</button>')
for kind,key,label in (('GROUP','groupChat','전체 대화방'),('DIRECT','directChat','1:1 대화방')):
    old=f'data-chat-kind="{kind}" data-label="실시간 대화방 · '+('전체' if kind=='GROUP' else '1:1')+f'">{label}</button>'
    new=old.replace(f'>{label}</button>',f'" class="work-menu"><span>{label}</span>'+badge(key)+'</button>').replace('"" class','" class')
    replace('static/admin.html',old,new)
replace('static/admin.html','<button data-view="communications">고객소통</button>',
        '<button class="work-menu" data-view="communications" data-label="고객소통"><span>고객소통</span>'+badge('communications')+'</button>')
replace('static/admin.html','<a href="returns-admin.html">반품·교환 관리</a>',
        '<a class="work-menu" href="returns-admin.html"><span>반품·교환 관리</span>'+badge('returnTotal')+'</a>')

admin=Path('static/admin.html');text=admin.read_text()
start=text.index('function renderComms(){');end=text.index('async function legacyImport()',start)
text=text[:start]+(source/'render-comms.js').read_text()+'\n'+text[end:]
needle="if(q.get('view')==='orders'){const scope=q.get('scope')==='cancel'?'cancel':'all';document.querySelector(`[data-view=\"orders\"][data-order-scope=\"${scope}\"]`).click()}"
assert text.count(needle)==1
text=text.replace(needle,needle+"else if(q.get('view')==='liveChat'){document.querySelector('[data-chat-kind=\"'+(q.get('kind')==='DIRECT'?'DIRECT':'GROUP')+'\"]').click()}else if(q.get('view')==='communications'){document.querySelector('[data-view=\"communications\"]').click()}")
admin.write_text(text)

extra='<div class="event-links">'
for href,key,label in (
    ('admin.html?view=orders','orders','주문·배송'),
    ('admin.html?view=orders&amp;scope=cancel','cancellations','취소 신청'),
    ('returns-admin.html?type=RETURN&amp;active=1','returns','반품'),
    ('returns-admin.html?type=EXCHANGE&amp;active=1','exchanges','교환'),
    ('admin.html?view=liveChat&amp;kind=GROUP','groupChat','전체 대화방'),
    ('admin.html?view=liveChat&amp;kind=DIRECT','directChat','1:1 대화방'),
    ('admin.html?view=communications','communications','고객소통')):
    extra+=f'<a class="work-menu" href="{href}"><span>{label}</span>'+badge(key)+'</a>'
extra+='</div>'
for page in ('naver-admin','design-studio'):
    replace(f'static/{page}.html','</aside>',extra+'</aside>')
    replace(f'static/{page}.html','</head>','<link rel="stylesheet" href="assets/admin-workflow.css"></head>')

for href,key,label in (('admin.html?view=liveChat&amp;kind=GROUP','groupChat','전체 대화방'),('admin.html?view=liveChat&amp;kind=DIRECT','directChat','1:1 대화방'),('admin.html?view=communications','communications','고객소통')):
    replace('static/returns-admin.html','<p class="work-help">',f'<a class="work-menu" href="{href}"><span>{label}</span>'+badge(key)+'</a><p class="work-help">')

for name in ('admin','returns-admin','design-studio','naver-admin'):
    path=Path('static')/(name+'.html');text=path.read_text()
    text=text.replace('<script src="assets/admin-workflow.js"></script>','')
    text=text.replace('30초마다 자동 갱신','5초마다 갱신 · 미확인 대화·문의는 확인 시 감소')
    text=text.replace('</head>','<link rel="stylesheet" href="assets/admin-events.css?v=21-events-1"></head>')
    text=text.replace('</body>','<script src="assets/admin-events.js?v=21-events-1"></script></body>')
    if name=='admin':text=text.replace('assets/chat.js?v=21-member-1','assets/chat.js?v=21-events-1')
    path.write_text(text)

# A room is read only when its latest displayed customer message is visible.
replace('static/assets/chat.js','log.scrollTop=log.scrollHeight;}','log.scrollTop=log.scrollHeight;notifyRead();}')
replace('static/assets/chat.js','    function stream(g){',
        "    function notifyRead(){if(!admin||!active||!room)return;const through=Math.max(0,...[...messages.values()].filter(m=>m.senderRole!=='admin').map(m=>m.id));window.AdminNotifications?.chatVisible({room:room.id,kind:room.kind,through,log})}\n    log.addEventListener('scroll',notifyRead);\n    window.addEventListener('focus',notifyRead);\n    function stream(g){")
replace('static/assets/chat.js','<b>${esc(x.name)}</b><small>',
        '<b>${esc(x.name)}</b>${admin&&window.AdminNotifications?.roomCount(x.id)?`<span class="event-unread">${window.AdminNotifications.roomCount(x.id)}</span>`:\'\'}<small>')
print('V21 administrator unread counters and event sounds applied')
