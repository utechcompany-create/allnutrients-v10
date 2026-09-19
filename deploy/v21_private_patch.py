"""Add private questions after the V21 customer/admin overlays."""
from pathlib import Path
from shutil import copyfile


def replace(path, old, new, count=1):
    file = Path(path)
    text = file.read_text()
    if text.count(old) != count:
        raise SystemExit(f'Expected {count} private-inquiry target(s) in {path}: {old[:80]}')
    file.write_text(text.replace(old, new))


source = Path(__file__).resolve().parent / 'v21_private'
for relative in ('app/communications.py', 'static/assets/private-inquiries.js', 'static/assets/private-inquiries.css'):
    destination = Path(relative)
    destination.parent.mkdir(parents=True, exist_ok=True)
    copyfile(source / relative, destination)

main = Path('app/main.py')
text = main.read_text()
start = text.index('@app.get("/api/board")')
end = text.index('@app.post("/api/admin/legacy-import")', start)
main.write_text(text[:start] + 'from . import communications\napp.include_router(communications.router)\n\n' + text[end:])

checkbox = '<label class="full privacy-option"><input type="checkbox" name="isPrivate"><span>비밀글로 작성<small>제목, 내용과 답변은 작성자와 관리자만 볼 수 있습니다.</small></span></label>'
replace('static/board.html', '<form id="form" class="grid2">', '<form id="form" class="grid2">' + checkbox.replace('name="isPrivate"', 'name="isPrivate" id="boardPrivate"') + '<p class="full privacy-state" id="privacyState" aria-live="polite">공개글은 모든 방문자가 볼 수 있습니다.</p>')
replace('static/board.html', '<button class="btn primary full">등록</button>', '<button class="btn primary full" id="boardSubmit">공개글 등록</button>')
replace('static/board.html', '<h2>새 글</h2>', '<h2 id="composeTitle">공개글 쓰기</h2>')
replace('static/board.html', '<button class="btn primary" id="writeBtn">글쓰기</button>', '<button class="btn ghost" id="writeBtn">공개글 쓰기</button>')
replace('static/board.html', '<section class="card"><div class="filters"', '<aside class="privacy-help"><div><strong>비공개 문의가 필요하신가요?</strong><p>비밀글의 제목, 내용과 답변은 작성자와 관리자만 확인할 수 있습니다.</p></div><button class="btn primary" id="privateWriteBtn" type="button">🔒 비밀글 쓰기</button></aside><section class="card"><div class="filters"')
replace('static/detail.html', '<div class="full"><button class="btn primary">상품 문의 등록</button></div>', checkbox + '<div class="full"><button class="btn primary">상품 문의 등록</button></div>')
for page in ('static/board.html', 'static/detail.html'):
    replace(page, "content:f.get('content')", "content:f.get('content'),isPrivate:f.get('isPrivate')==='on'")
    replace(page, '</head>', '<link rel="stylesheet" href="assets/private-inquiries.css?v=21-entry-2"></head>')
    replace(page, '<script src="assets/api.js"></script>', '<script src="assets/api.js"></script><script src="assets/private-inquiries.js?v=21-entry-2"></script>')

board = Path('static/board.html')
text = board.read_text()
start = text.index('function render(){')
end = text.index('async function load()', start)
text = text[:start] + '''function render(){filters.innerHTML=cats.map(c=>`<button class="chip ${c===current?'active':''}" data-cat="${c}">${c}</button>`).join('');const rows=posts.filter(p=>current==='전체'||p.category===current);list.innerHTML=rows.length?rows.map(p=>PrivateInquiryUI.card(p,'board')).join(''):'<p class="muted">등록된 글이 없습니다.</p>'}
''' + text[end:]
text = text.replace("async function load(){posts=await api('/api/board');render()}", "let boardLoadId=0;async function load(){const seq=++boardLoadId;try{const next=await api('/api/board');if(seq!==boardLoadId)return;posts=next;render()}catch(e){if(seq!==boardLoadId)return;posts=[];list.innerHTML='<p class=\"muted\">게시글을 불러오지 못했습니다. 다시 시도해 주세요.</p>'}}")
old_open="writeBtn.onclick=async()=>{const me=await api('/api/auth/me');if(!me.authenticated){location.href='login.html?next=board.html';return}modal.classList.add('open')}"
if text.count(old_open)!=1:
    raise SystemExit('Expected original board compose handler')
text=text.replace(old_open,'''let composeRequest=0;
function updatePrivacyState(){const isPrivate=document.getElementById('boardPrivate').checked;document.getElementById('composeTitle').textContent=isPrivate?'비밀글 쓰기':'공개글 쓰기';document.getElementById('boardSubmit').textContent=isPrivate?'비밀글 등록':'공개글 등록';document.getElementById('privacyState').textContent=isPrivate?'비밀글: 작성자와 관리자만 제목, 내용과 답변을 볼 수 있습니다.':'공개글: 모든 방문자가 제목, 내용과 답변을 볼 수 있습니다.'}
async function openCompose(isPrivate){const request=++composeRequest;try{const me=await api('/api/auth/me');if(request!==composeRequest)return;if(!me.authenticated){location.href='login.html?next='+encodeURIComponent('board.html?compose='+(isPrivate?'private':'public'));return}form.reset();document.getElementById('boardPrivate').checked=isPrivate;updatePrivacyState();modal.classList.add('open')}catch(e){toastMsg(e.message)}}
writeBtn.onclick=()=>openCompose(false);document.getElementById('privateWriteBtn').onclick=()=>openCompose(true);document.getElementById('boardPrivate').onchange=updatePrivacyState''')
text = text.replace('}load();', """}async function makePrivate(id){if(!confirm('이 글의 제목, 내용과 모든 답변을 작성자와 관리자만 볼 수 있는 비밀글로 변경할까요?'))return;try{await api('/api/board/'+encodeURIComponent(id)+'/private',{method:'POST'});await load();toastMsg('비밀글로 변경했습니다.')}catch(e){toastMsg(e.message)}}list.onclick=e=>{const secret=e.target.closest('[data-private-id]');if(secret){makePrivate(secret.dataset.privateId);return}const b=e.target.closest('[data-follow-id]');if(b)follow(b.dataset.followId)};PrivateInquiryUI.watch(()=>{boardLoadId++;posts=[];list.textContent='게시글을 불러오는 중입니다.'},load);load();const composeMode=new URLSearchParams(location.search).get('compose');if(composeMode==='private'||composeMode==='public')openCompose(composeMode==='private');""")
board.write_text(text)

detail = Path('static/detail.html')
text = detail.read_text()
start = text.index('async function renderInquiries(){')
end = text.index('if(!p){', start)
text = text[:start] + '''let inquiryLoadId=0;async function renderInquiries(){const seq=++inquiryLoadId;try{const list=await api('/api/inquiries?productId='+encodeURIComponent(p.id));if(seq!==inquiryLoadId)return;inquiryList.innerHTML=list.length?list.map(q=>PrivateInquiryUI.card(q,'inquiry')).join(''):'<div class="muted">등록된 문의가 없습니다.</div>'}catch(e){if(seq!==inquiryLoadId)return;inquiryList.innerHTML='<div class="muted">문의를 불러오지 못했습니다.</div>'}}
PrivateInquiryUI.watch(()=>{inquiryLoadId++;const el=document.getElementById('inquiryList');if(el)el.textContent='문의를 불러오는 중입니다.'},()=>{if(p)return renderInquiries()});
''' + text[end:]
detail.write_text(text)
replace('static/admin.html', '${esc(x.title)}', '${x.isPrivate?\'<span class="badge">🔒 비밀글</span> \':\'\'}${esc(x.title)}', count=2)
print('V21 private inquiries and board threads applied')
