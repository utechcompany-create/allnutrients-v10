"""Apply sales reports and authenticated realtime chat after the V21 overlays."""
from pathlib import Path
from shutil import copyfile

source = Path(__file__).resolve().parent / 'v21_operations'
for relative in ('app/sales.py','app/chat.py','static/chat.html','static/assets/chat.js',
                 'static/assets/admin-operations.js','static/assets/operations.css'):
    destination = Path(relative)
    destination.parent.mkdir(parents=True,exist_ok=True)
    copyfile(source / relative,destination)

def replace(path,old,new):
    file=Path(path);text=file.read_text()
    if text.count(old)!=1:
        raise SystemExit(f'Expected one operations target in {path}: {old[:80]}')
    file.write_text(text.replace(old,new))

replace('app/main.py','app.include_router(communications.router)',
        'app.include_router(communications.router)\nfrom . import sales, chat\napp.include_router(sales.router)\napp.include_router(chat.router)')
replace('static/admin.html','<button data-view="members">',
        '<button data-view="sales">매출 관리</button><button type="button" id="chatMenuToggle" aria-expanded="true" aria-controls="chatSubnav">실시간 대화방 ▾</button><div id="chatSubnav" class="chat-subnav"><button data-view="liveChat" data-chat-kind="GROUP" data-label="실시간 대화방 · 전체">전체 대화방</button><button data-view="liveChat" data-chat-kind="DIRECT" data-label="실시간 대화방 · 1:1">1:1 대화방</button></div><button data-view="members">')
replace('static/admin.html','</main></div>',(source/'admin-sections.html').read_text()+'\n</main></div>')
replace('static/admin.html','</head>','<link rel="stylesheet" href="assets/operations.css"></head>')
replace('static/admin.html','</body>','<script src="assets/chat.js"></script><script src="assets/admin-operations.js"></script></body>')
for page in ('static/mypage.html','static/board.html'):
    replace(page,'<a class="btn ghost" href="index.html">쇼핑몰</a>',
            '<a class="btn ghost" href="index.html">쇼핑몰</a><a class="btn ghost" href="chat.html">실시간 대화방</a>')
print('V21 sales management and shared/private realtime chat applied')
