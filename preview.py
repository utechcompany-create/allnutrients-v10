import os, sqlite3, secrets, json
from pathlib import Path
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, FileResponse, RedirectResponse, Response as FastResponse
from fastapi.staticfiles import StaticFiles

DB=Path("preview.db")
app=FastAPI(title="올영양소 V10 Render Preview")
app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")
ADMIN_EMAIL=os.getenv("ADMIN_EMAIL","admin@allnutrients.local")
ADMIN_PASSWORD=os.getenv("ADMIN_PASSWORD","ChangeMe!2026")
SESSIONS={}

def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
    c.executescript("""
    create table if not exists products(id text primary key,code text,name text,price integer,compare_at integer,stock integer,status text,category text,origin text,capacity text,description text,emoji text);
    create table if not exists orders(id text primary key,name text,email text,phone text,total integer,status text,payment text,created text);
    create table if not exists returns(id text primary key,order_id text,type text,reason text,status text,created text);
    """)
    if c.execute("select count(*) from products").fetchone()[0]==0:
        c.executemany("insert into products values(?,?,?,?,?,?,?,?,?,?,?,?)",[
          ("P1001","RFC-COCO-1000","RFC 코코넛워터",15900,18900,120,"판매중","코코넛워터","베트남","1L","깔끔하고 시원하게 즐기는 데일리 코코넛워터","🥥"),
          ("P1002","TANDO-GINGER-99","탄도 생강즙 99%",21900,24900,80,"판매중","채소·뿌리","베트남","제품별 상이","생강의 알싸하고 깊은 풍미를 담은 진한 한 병","🫚"),
          ("P1003","RFC-NONI","RFC 노니주스",26900,29900,65,"판매중","과일주스","베트남","제품별 상이","노니 특유의 진한 풍미를 간편하게 즐기는 주스","🍐"),
          ("P1004","CABBAGE-JUICE","양배추즙",18900,21900,40,"판매중","채소·뿌리","베트남","제품별 상이","부담 없이 매일 챙겨 마시기 좋은 채소 주스","🥬")])
        c.commit()
    return c

def admin(request):
    token=request.cookies.get("adm")
    if not token or token not in SESSIONS: raise HTTPException(401,"관리자 로그인이 필요합니다.")

def page(title,body):
    return HTMLResponse(f"""<!doctype html><html lang=ko><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>{title}</title><style>
    body{{font-family:system-ui,sans-serif;margin:0;background:#f6f8f4;color:#183226}}header{{background:#173126;color:white;padding:18px}}main{{max-width:1000px;margin:auto;padding:28px}}.card{{background:white;border:1px solid #dfe7e0;border-radius:16px;padding:18px;margin:14px 0}}button,a{{padding:10px 14px;border:0;border-radius:10px;background:#2f7d4e;color:white;text-decoration:none;cursor:pointer}}input,select,textarea{{padding:10px;border:1px solid #ccd6ce;border-radius:8px;width:100%;box-sizing:border-box;margin:5px 0 12px}}table{{width:100%;border-collapse:collapse}}td,th{{padding:9px;border-bottom:1px solid #eee;text-align:left}}.muted{{color:#6d7c72}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}@media(max-width:700px){{.grid{{grid-template-columns:1fr}}}}
    </style><header><b>올영양소 V10</b></header><main>{body}</main></html>""")

@app.on_event("startup")
def startup():
    c=db(); c.close()

@app.get("/api/health")
def health(): return {"ok":True,"version":"10-v6-ui-preview","https":True}

@app.get("/api/auth/me")
def auth_me(): return {"authenticated":False}

@app.get("/api/bootstrap.js")
def bootstrap():
    c=db(); rows=c.execute("select * from products order by id").fetchall(); c.close()
    products=[{"id":r["id"],"code":r["code"],"name":r["name"],"category":r["category"],"price":r["price"],"compareAt":r["compare_at"],"stock":r["stock"],"status":r["status"],"origin":r["origin"],"capacity":r["capacity"],"description":r["description"],"emoji":r["emoji"],"image":"","detailTitle":r["name"],"detailText":r["description"],"detailImages":[]} for r in rows]
    design={
      "version":6,"brandName":"올영양소","announcement":"올영양소 공식몰 · 5만원 이상 무료배송",
      "brandColor":"#2f7d4e","inkColor":"#183226","bgColor":"#f6f8f4","topColor":"#173126",
      "heroStart":"#dcefbf","heroEnd":"#f4f8df","storyColor":"#173126","productCols":4,"cardRadius":22,"showAnnouncement":True,
      "slider":{"autoplay":True,"seconds":5},
      "banners":[{"id":"banner-main","name":"메인 배너","eyebrow":"ALL NUTRIENTS","title":"매일 한 병,\n영양을 더 쉽게.","text":"과일과 채소의 맛을 일상 속에서 간편하게. 올영양소의 주스 컬렉션을 만나보세요.","button":"상품 보러가기","href":"#products","image":"","mobileImage":"","alt":"올영양소 메인 배너","visible":True,"layout":"split","color":"#dcefbf","endColor":"#f4f8df"}],
      "categories":[{"id":"cat-1","name":"코코넛워터","source":"코코넛워터","visible":True},{"id":"cat-2","name":"채소·뿌리","source":"채소·뿌리","visible":True},{"id":"cat-3","name":"과일주스","source":"과일주스","visible":True}],
      "sections":[
        {"id":"hero","type":"banners","name":"메인 배너","visible":True},
        {"id":"products","type":"products","name":"전체상품","eyebrow":"SHOP","title":"오늘의 영양 한 병","text":"원하는 맛과 라이프스타일에 맞춰 골라보세요.","showFilters":True,"mode":"all","source":"","productIds":[],"limit":0,"visible":True},
        {"id":"best","type":"products","name":"베스트 · 추천상품","eyebrow":"OUR PICKS","title":"함께 만나보는 추천 상품","text":"마음에 드는 한 병을 골라보세요.","showFilters":False,"mode":"selected","source":"","productIds":["P1001","P1002","P1003","P1004"],"limit":4,"visible":True},
        {"id":"story","type":"text","name":"브랜드스토리","eyebrow":"OUR STORY","title":"필요한 영양을 복잡하지 않게.","text":"올영양소는 과일·채소·뿌리 원료 기반 음료를 한곳에서 편하게 고를 수 있는 전문몰을 지향합니다.","bg":"#173126","color":"#ffffff","align":"left","button":"","href":"","visible":True}
      ],
      "navigation":[{"id":"menu-all","name":"전체상품","kind":"section","target":"products","visible":True},{"id":"menu-best","name":"베스트","kind":"section","target":"best","visible":True},{"id":"menu-brand","name":"브랜드","kind":"section","target":"story","visible":True},{"id":"menu-board","name":"고객게시판","kind":"page","target":"board.html","visible":True}]
    }
    payload=json.dumps({"products":products,"design":design},ensure_ascii=False).replace("</","<\\/")
    js=f"window.SERVER_BOOTSTRAP={payload};try{{localStorage.setItem('allnutrients-products-v2',JSON.stringify(window.SERVER_BOOTSTRAP.products));localStorage.setItem('allnutrients-design-v1',JSON.stringify(window.SERVER_BOOTSTRAP.design));}}catch(e){{console.warn(e)}}"
    return FastResponse(js,media_type="application/javascript",headers={"Cache-Control":"no-store"})

@app.get("/")
@app.get("/index.html")
def home(): return FileResponse("static/index.html")

@app.get("/guest-order.html")
@app.get("/guest-order")
def guest_order():
    c=db(); ps=c.execute("select * from products").fetchall(); c.close()
    opts="".join([f"<option value='{p['id']}'>{p['name']} - {p['price']:,}원</option>" for p in ps])
    return page("비회원 주문",f"""<h1>비회원 주문 테스트</h1><div class=card><label>상품<select id=p>{opts}</select></label><label>이름<input id=n></label><label>이메일<input id=e type=email></label><label>연락처<input id=ph></label><button onclick=go()>주문 생성</button><pre id=o></pre></div><script>async function go(){{let r=await fetch('/api/orders',{{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify({{productId:p.value,name:n.value,email:e.value,phone:ph.value}})}});o.textContent=JSON.stringify(await r.json(),null,2)}}</script>""")

@app.get("/login.html")
def login_page(): return page("회원 로그인","<h1>로그인</h1><p class=muted>현재 HTTPS 검증 단계입니다. 회원/결제 전체 UI는 원본 V10 운영본으로 교체됩니다.</p><a href='/'>쇼핑몰로</a>")

@app.get("/checkout.html")
def checkout_page(): return RedirectResponse("/guest-order.html")

@app.get("/detail.html")
def detail_page(id:str=""): return page("상품 상세",f"<h1>상품 상세</h1><p>상품 ID: {id}</p><a href='/'>쇼핑몰로</a>")

@app.get("/board.html")
def board_page(): return page("고객게시판","<h1>고객게시판</h1><p class=muted>V10 서버형 고객게시판 연결 예정입니다.</p><a href='/'>쇼핑몰로</a>")

@app.post("/api/orders")
async def create_order(request:Request):
    d=await request.json(); c=db(); p=c.execute("select * from products where id=?",(d.get("productId"),)).fetchone()
    if not p: raise HTTPException(404,"상품 없음")
    oid="ON"+secrets.token_hex(6).upper()
    c.execute("insert into orders values(?,?,?,?,?,?,?,datetime('now'))",(oid,d.get("name",""),d.get("email",""),d.get("phone",""),p["price"],"ORDERED","CASH")); c.commit(); c.close()
    return {"orderNo":oid,"totalAmount":p["price"],"status":"ORDERED"}

@app.get("/api/orders/{oid}")
def get_order(oid:str,email:str="",phone:str=""):
    c=db(); o=c.execute("select * from orders where id=?",(oid,)).fetchone(); c.close()
    if not o: raise HTTPException(404,"주문 없음")
    if email and o["email"]!=email: raise HTTPException(403,"정보 불일치")
    if phone and o["phone"]!=phone: raise HTTPException(403,"정보 불일치")
    return dict(o)

@app.get("/return-request.html")
@app.get("/return-request")
def return_page(orderId:str=""):
    return page("반품·교환 신청",f"""<h1>반품·교환 신청</h1><div class=card><label>주문번호<input id=oid value='{orderId}'></label><label>구분<select id=t><option value=RETURN>반품</option><option value=EXCHANGE>교환</option></select></label><label>사유<textarea id=r></textarea></label><button onclick=go()>신청</button><pre id=o></pre></div><script>async function go(){{let x=await fetch('/api/returns',{{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify({{orderId:oid.value,type:t.value,reason:r.value}})}});o.textContent=JSON.stringify(await x.json(),null,2)}}</script>""")

@app.post("/api/returns")
async def create_return(request:Request):
    d=await request.json(); c=db()
    if not c.execute("select 1 from orders where id=?",(d.get("orderId"),)).fetchone(): raise HTTPException(404,"주문 없음")
    rid="RT"+secrets.token_hex(5).upper()
    c.execute("insert into returns values(?,?,?,?,?,datetime('now'))",(rid,d.get("orderId"),d.get("type"),d.get("reason",""),"REQUESTED")); c.commit(); c.close()
    return {"returnId":rid,"status":"REQUESTED"}

@app.get("/admin-login")
@app.get("/admin-login.html")
def admin_login():
    return page("관리자 로그인","""<h1>관리자 로그인</h1><div class=card><input id=e placeholder='이메일'><input id=p type=password placeholder='비밀번호'><button onclick=go()>로그인</button><div id=o></div></div><script>async function go(){let r=await fetch('/api/admin/login',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({email:e.value,password:p.value})});let d=await r.json();if(r.ok)location='/admin.html';else o.textContent=d.detail||'실패'}</script>""")

@app.post("/api/admin/login")
async def login(request:Request,response:Response):
    d=await request.json()
    if d.get("email")!=ADMIN_EMAIL or d.get("password")!=ADMIN_PASSWORD: raise HTTPException(401,"로그인 실패")
    token=secrets.token_urlsafe(32); SESSIONS[token]=True; response.set_cookie("adm",token,httponly=True,secure=True,samesite="lax")
    return {"ok":True}

@app.get("/admin")
@app.get("/admin.html")
def admin_page(request:Request):
    try: admin(request)
    except HTTPException: return RedirectResponse("/admin-login.html")
    c=db(); orders=c.execute("select * from orders order by created desc").fetchall(); returns=c.execute("select * from returns order by created desc").fetchall(); c.close()
    orows="".join([f"<tr><td>{x['id']}</td><td>{x['name']}</td><td>{x['total']:,}</td><td>{x['status']}</td></tr>" for x in orders]) or "<tr><td colspan=4>없음</td></tr>"
    rrows="".join([f"<tr><td>{x['id']}</td><td>{x['order_id']}</td><td>{x['type']}</td><td>{x['status']}</td></tr>" for x in returns]) or "<tr><td colspan=4>없음</td></tr>"
    return page("관리자",f"<h1>관리자</h1><div class=card><h2>주문</h2><table><tr><th>주문번호</th><th>고객</th><th>금액</th><th>상태</th></tr>{orows}</table></div><div class=card><h2>반품·교환</h2><table><tr><th>신청번호</th><th>주문번호</th><th>구분</th><th>상태</th></tr>{rrows}</table></div><p><a href='/naver/ep.txt'>네이버 EP 확인</a></p>")

@app.get("/naver/ep.txt")
def ep(request:Request):
    base=str(request.base_url).rstrip("/"); c=db(); ps=c.execute("select * from products where stock>0").fetchall(); c.close()
    head="id\ttitle\tprice_pc\tlink\timage_link\tcategory_name1\tshipping\torigin"
    rows=[head]+[f"{p['id']}\t{p['name']}\t{p['price']}\t{base}/\t{base}/favicon.ico\t{p['category']}\t0\t{p['origin']}" for p in ps]
    return PlainTextResponse("\n".join(rows),media_type="text/plain; charset=utf-8")
