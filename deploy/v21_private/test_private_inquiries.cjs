const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
process.chdir(__dirname);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const settle=async()=>{for(let i=0;i<20;i++)await Promise.resolve()};
const secret={id:'secret-1',isPrivate:true,canRead:true,canFollowup:true,title:'SECRET_TITLE',content:'SECRET_CONTENT <img onerror=1>',author:'SECRET_AUTHOR',category:'배송문의',status:'답변완료',createdAt:'2026-09-19T00:00:00Z',messages:[{role:'seller',content:'SECRET_REPLY'}]};
const helper=fs.readFileSync('static/assets/private-inquiries.js','utf8');
function context(kind,query=''){
  const els={},calls=[],events={};let items=[{...secret,canRead:false,canFollowup:false}],deferred=null,authenticated=true,confirmation=true;
  function element(id){if(!els[id]){let markup='';els[id]={value:'',values:{category:'배송문의',title:'내 제목',content:'내 내용'},classList:{add(){},remove(){}},reset(){delete this.values.isPrivate}};Object.defineProperties(els[id],{innerHTML:{get:()=>markup,set:v=>{markup=v}},textContent:{get:()=>markup,set:v=>{markup=v}}});}return els[id];}
  Object.defineProperty(element('boardPrivate'),'checked',{get:()=>element('form').values.isPrivate==='on',set:v=>{if(v)element('form').values.isPrivate='on';else delete element('form').values.isPrivate}});
  const api=async(path,options={})=>{calls.push({path,options});if(path==='/api/auth/me')return {authenticated};if(options.method==='POST')return {ok:true};if(path==='/api/board'||path.startsWith('/api/inquiries?')){if(deferred){const pending=deferred;deferred=null;return pending}return items}throw Error(path)};
  const window={addEventListener(k,fn){events[k]=fn}};
  let locationURL=new URL('https://test.invalid/'+(kind==='board'?'board.html'+query:'detail.html?id=P1001'));
  const location={get href(){return locationURL.href},set href(v){locationURL=new URL(v,locationURL)},get search(){return locationURL.search},get searchParams(){return locationURL.searchParams}};
  const ctx=vm.createContext({window,document:{getElementById:element},AppAPI:{api,esc,money:n=>n+'원'},ShopCore:{productList:()=>[{id:'P1001',name:'테스트 상품',price:10000,stock:10,options:[]}]},location,URLSearchParams,FormData:class{constructor(form){this.form=form}get(key){return this.form.values[key]??null}},setTimeout(){},alert(){},confirm:()=>confirmation,console});
  for(const id of ['toast','filters','list','writeBtn','modal','form','app','inquiryList','inquiryForm'])ctx[id]=element(id);
  vm.runInContext(helper,ctx);ctx.PrivateInquiryUI=window.PrivateInquiryUI;
  const page=fs.readFileSync('static/'+(kind==='board'?'board.html':'detail.html'),'utf8');
  assert.match(page,/type="checkbox" name="isPrivate"/);
  const script=[...page.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]).join('\n');vm.runInContext(script,ctx);
  return {ctx,events,calls,element,setItems:x=>{items=x},defer:x=>{deferred=x},setAuthenticated:x=>{authenticated=x},setConfirmation:x=>{confirmation=x},list:element(kind==='board'?'list':'inquiryList'),form:element(kind==='board'?'form':'inquiryForm')};
}
(async()=>{
  for(const kind of ['board','inquiry']){
    const t=context(kind);await settle();
    assert.match(t.list.innerHTML,/비밀글입니다/);assert.doesNotMatch(t.list.innerHTML,/SECRET_|data-follow-id/);
    t.form.values.isPrivate='on';await t.form.onsubmit({preventDefault(){},target:t.form});
    const endpoint=kind==='board'?'/api/board':'/api/inquiries';
    assert.equal(t.calls.filter(x=>x.path===endpoint&&x.options.method==='POST').at(-1).options.body.isPrivate,true);
    await t.form.onsubmit({preventDefault(){},target:t.form});
    assert.equal(t.calls.filter(x=>x.path===endpoint&&x.options.method==='POST').at(-1).options.body.isPrivate,false);
    t.setItems([secret]);t.events.focus();await settle();
    assert.match(t.list.innerHTML,/SECRET_TITLE/);assert.match(t.list.innerHTML,/SECRET_REPLY/);assert.match(t.list.innerHTML,/&lt;img/);assert.doesNotMatch(t.list.innerHTML,/<img/);
    if(kind==='board')assert.match(t.list.innerHTML,/data-follow-id/);
    t.events.pagehide();assert.doesNotMatch(t.list.innerHTML,/SECRET_/);
    t.setItems([{...secret,canRead:false,canFollowup:false}]);t.events.pageshow({persisted:true});await settle();assert.doesNotMatch(t.list.innerHTML,/SECRET_/);
    // A previous account's delayed response cannot overwrite the refreshed list.
    let resolve;t.defer(new Promise(r=>resolve=r));t.events.focus();await settle();
    t.events.focus();await settle();resolve([secret]);await settle();assert.doesNotMatch(t.list.innerHTML,/SECRET_/);
  }
  const t=context('board');await settle();
  await t.element('privateWriteBtn').onclick();
  assert.equal(t.element('boardPrivate').checked,true);
  assert.equal(t.element('boardSubmit').textContent,'비밀글 등록');
  assert.match(t.element('privacyState').textContent,/작성자와 관리자만/);
  await t.form.onsubmit({preventDefault(){},target:t.form});
  assert.equal(t.calls.filter(x=>x.path==='/api/board'&&x.options.method==='POST').at(-1).options.body.isPrivate,true);
  await t.element('writeBtn').onclick();assert.equal(t.element('boardPrivate').checked,false);
  assert.equal(t.element('boardSubmit').textContent,'공개글 등록');
  t.element('boardPrivate').checked=true;t.element('boardPrivate').onchange();
  assert.equal(t.element('composeTitle').textContent,'비밀글 쓰기');
  t.setItems([{...secret,isPrivate:false,canMakePrivate:true}]);t.events.focus();await settle();
  assert.match(t.list.innerHTML,/data-private-id="secret-1"/);
  t.setConfirmation(false);await t.ctx.makePrivate('secret-1');assert.ok(!t.calls.some(x=>x.path.endsWith('/private')));
  t.setConfirmation(true);await t.ctx.makePrivate('secret-1');assert.equal(t.calls.find(x=>x.path.endsWith('/private')).options.method,'POST');
  t.setAuthenticated(false);await t.element('privateWriteBtn').onclick();
  assert.equal(t.ctx.location.searchParams.get('next'),'board.html?compose=private');
  const returned=context('board','?compose=private');await settle();assert.equal(returned.element('boardPrivate').checked,true);
  console.log('PASS: explicit private/public entry, login return mode, submitted privacy flag, existing-post conversion, locked rendering, escaping and stale-response protection');
})().catch(e=>{console.error(e);process.exitCode=1});
