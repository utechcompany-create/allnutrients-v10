import os, sqlite3, secrets, hashlib, hmac, json
from pathlib import Path
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse

DB=Path("preview.db")
app=FastAPI(title="올영양소 V10 Render Preview")
ADMIN_EMAIL=os.getenv("ADMIN_EMAIL","admin@allnutrients.local")
ADMIN_PASSWORD=os.getenv("ADMIN_PASSWORD","ChangeMe!2026")
SECRET=os.getenv("APP_SECRET","allnutrients-preview-secret")
SESSIONS={}

def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
    c.executescript("""
    create table if not exists products(id text primary key,name text,price integer,stock integer,category text,origin text);
    create table if not exists orders(id text primary key,name text,email text,phone text,total integer,status text,payment text,created text);
    create table if not exists returns(id text primary key,order_id text,type text,reason text,status text,created text);
    """)
    if c.execute("select count(*) from products").fetchone()[0]==0:
        c.executemany("insert into products values(?,?,?,?,?,?)",[
          ("P1001","RFC 코코넛워터",15900,120,"코코넛워터","베트남"),
          ("P1002","탄도 생강즙 99%",21900,80,"채소·뿌리","베트남"),
          ("P1003","RFC 노니주스",26900,65,"과일주스","베트남"),
          ("P1004","양배추즙",18900,40,"채소·뿌리","베트남")])
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
def health(): return {"ok":True,"version":"10-preview","https":True}

@app.get("/")
def home():
    c=db(); ps=c.execute("select * from products").fetchall(); c.close()
    cards="".join([f"<div class=card><h3>{p['name']}</h3><p>{p['price']:,}원 · 재고 {p['stock']}</p></div>" for p in ps])
    return page("올영양소",f"<h1>올영양소 온라인몰</h1><p class=muted>Render HTTPS 검증 빌드</p><div class=grid>{cards}</div><p><a href='/guest-order'>비회원 주문</a> <a href='/admin-login'>관리자</a></p>")

@app.get("/guest-order")
def guest_order():
    c=db(); ps=c.execute("select * from products").fetchall(); c.close()
    opts="".join([f"<option value='{p['id']}'>{p['name']} - {p['price']:,}원</option>" for p in ps])
    return page("비회원 주문",f"""<h1>비회원 주문 테스트</h1><div class=card><label>상품<select id=p>{opts}</select></label><label>이름<input id=n></label><label>이메일<input id=e type=email></label><label>연락처<input id=ph></label><button onclick=go()>주문 생성</button><pre id=o></pre></div><script>async function go(){{let r=await fetch('/api/orders',{{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify({{productId:p.value,name:n.value,email:e.value,phone:ph.value}})}});o.textContent=JSON.stringify(await r.json(),null,2)}}</script>""")

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
def admin_login():
    return page("관리자 로그인","""<h1>관리자 로그인</h1><div class=card><input id=e placeholder='이메일'><input id=p type=password placeholder='비밀번호'><button onclick=go()>로그인</button><div id=o></div></div><script>async function go(){let r=await fetch('/api/admin/login',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({email:e.value,password:p.value})});let d=await r.json();if(r.ok)location='/admin';else o.textContent=d.detail||'실패'}</script>""")

@app.post("/api/admin/login")
async def login(request:Request,response:Response):
    d=await request.json()
    if d.get("email")!=ADMIN_EMAIL or d.get("password")!=ADMIN_PASSWORD: raise HTTPException(401,"로그인 실패")
    token=secrets.token_urlsafe(32); SESSIONS[token]=True; response.set_cookie("adm",token,httponly=True,secure=True,samesite="lax")
    return {"ok":True}

@app.get("/admin")
def admin_page(request:Request):
    admin(request); c=db(); orders=c.execute("select * from orders order by created desc").fetchall(); returns=c.execute("select * from returns order by created desc").fetchall(); c.close()
    orows="".join([f"<tr><td>{x['id']}</td><td>{x['name']}</td><td>{x['total']:,}</td><td>{x['status']}</td></tr>" for x in orders]) or "<tr><td colspan=4>없음</td></tr>"
    rrows="".join([f"<tr><td>{x['id']}</td><td>{x['order_id']}</td><td>{x['type']}</td><td>{x['status']}</td></tr>" for x in returns]) or "<tr><td colspan=4>없음</td></tr>"
    return page("관리자",f"<h1>관리자</h1><div class=card><h2>주문</h2><table><tr><th>주문번호</th><th>고객</th><th>금액</th><th>상태</th></tr>{orows}</table></div><div class=card><h2>반품·교환</h2><table><tr><th>신청번호</th><th>주문번호</th><th>구분</th><th>상태</th></tr>{rrows}</table></div><p><a href='/naver/ep.txt'>네이버 EP 확인</a></p>")

@app.get("/naver/ep.txt")
def ep(request:Request):
    base=str(request.base_url).rstrip("/"); c=db(); ps=c.execute("select * from products where stock>0").fetchall(); c.close()
    head="id\ttitle\tprice_pc\tlink\timage_link\tcategory_name1\tshipping\torigin"
    rows=[head]+[f"{p['id']}\t{p['name']}\t{p['price']}\t{base}/\t{base}/favicon.ico\t{p['category']}\t0\t{p['origin']}" for p in ps]
    return PlainTextResponse("\n".join(rows),media_type="text/plain; charset=utf-8")
