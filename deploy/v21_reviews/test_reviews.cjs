const fs=require('node:fs'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const settle=async()=>{for(let n=0;n<100;n++)await Promise.resolve()};
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function setup(html,url){
  const dom=new JSDOM(html,{url,runScripts:'outside-only',pretendToBeVisual:true}),w=dom.window;
  w.confirm=()=>true;w.HTMLDialogElement.prototype.showModal=function(){this.open=true};w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new w.Event('close'))};
  w.URL.createObjectURL=()=> 'blob:local-test';w.URL.revokeObjectURL=()=>{};return {dom,w,d:w.document};
}
(async()=>{
  const t=setup('<section id="productReviews"></section>','https://example.test/detail.html?id=P1001'),{w,d}=t,calls=[];
  let review=null,failed=false,uploaded=0;
  const purchase={orderItemId:7,orderNo:'ORDER-1',productId:'P1001',productName:'코코넛 <img onerror=alert(1)>',quantity:1,canWrite:true};
  w.AppAPI={esc,api:async(url,options={})=>{
    calls.push({url,options});
    if(url==='/api/auth/me')return {authenticated:true,role:'customer'};
    if(url.startsWith('/api/reviews/purchases?'))return {total:1,offset:0,limit:10,items:[{...purchase,review}]};
    if(url.startsWith('/api/reviews?'))return {total:review?1:0,average:review?.rating??null,offset:0,limit:10,items:review?[review]:[]};
    if(url==='/api/review-photos'&&options.method==='POST'){uploaded++;assert.equal(options.body.get('orderItemId'),'7');return {id:'photo1',url:'/api/review-photos/photo1'}}
    if(options.method==='POST'||options.method==='PUT'){
      if(failed)throw Error('저장 실패 테스트');
      review={...options.body,id:'review1',revision:review?review.revision+1:1,author:'김**',createdAt:'2026-09-19',photos:(options.body.photoIds||[]).map(id=>({id,url:'/api/review-photos/'+id}))};return review;
    }
    if(options.method==='DELETE'){review=null;return {ok:true}}
    throw Error('Unexpected '+url);
  }};
  w.eval(fs.readFileSync('static/assets/reviews.js','utf8'));await settle();
  assert.ok(d.querySelector('[data-review-edit]'));assert.equal(d.querySelector('#reviewOwnList img'),null,'product text cannot inject HTML');
  d.querySelector('[data-review-edit]').click();assert.ok(d.querySelector('dialog').open);
  d.querySelector('[name=rating][value="4"]').checked=true;d.getElementById('reviewContent').value='<script>alert(1)</script> 정말 맛있어요';
  const input=d.getElementById('reviewPhotoInput');
  Object.defineProperty(input,'files',{configurable:true,value:Array.from({length:6},()=>new w.File(['x'],'x.jpg',{type:'image/jpeg'}))});input.dispatchEvent(new w.Event('change'));
  assert.match(d.getElementById('reviewFormError').textContent,/최대 5장/);assert.equal(uploaded,0);
  Object.defineProperty(input,'files',{configurable:true,value:[new w.File(['photo'],'photo.jpg',{type:'image/jpeg'})]});input.dispatchEvent(new w.Event('change'));
  assert.equal(d.querySelectorAll('#reviewPhotoPreview img').length,1);
  const submit=()=>d.getElementById('reviewForm').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
  failed=true;submit();await settle();assert.ok(d.querySelector('dialog').open);assert.match(d.getElementById('reviewFormError').textContent,/저장 실패/);assert.equal(uploaded,1);
  failed=false;submit();await settle();assert.equal(uploaded,1,'retry reuses uploaded draft');assert.equal(d.querySelector('dialog').open,false);
  assert.equal(review.rating,4);assert.deepEqual([...review.photoIds],['photo1']);assert.equal(d.querySelector('#reviewPublicList script'),null);assert.equal(d.querySelectorAll('#reviewPublicList .review-photos img').length,1);
  d.querySelector('[data-review-edit]').click();assert.equal(d.querySelectorAll('#reviewPhotoPreview img').length,1);d.querySelector('[data-remove-photo]').click();submit();await settle();assert.equal(review.photoIds.length,0);assert.equal(review.revision,2);
  d.querySelector('[data-review-delete]').click();await settle();assert.equal(review,null);assert.match(d.getElementById('reviewSummary').textContent,/아직/);
  t.dom.window.close();

  const a=setup(fs.readFileSync('static/admin.html','utf8'),'https://example.test/admin.html'),aw=a.w,ad=a.d,adminCalls=[];let confirms=[];
  const row={id:'r1',productName:'상품',orderNo:'O1',author:'김**',createdAt:'2026-09-19',rating:2,content:'아쉬운 구매 후기',reply:'',photos:[{id:'p1',url:'/api/review-photos/p1'}],revision:3,hidden:false,unreadCount:1,notificationThrough:3};
  aw.AppAPI={esc,api:async(url,options={})=>{adminCalls.push({url,options});return options.method?{ok:true}:{total:1,offset:0,limit:20,items:[row]}}};
  aw.AdminNotifications={watchThreads(){},confirm:x=>confirms.push(x),refresh(){}};
  ad.getElementById('reviews').classList.add('active');aw.eval(fs.readFileSync('static/assets/admin-reviews.js','utf8'));await aw.reloadAdminReviews();await settle();
  assert.equal(ad.querySelectorAll('#adminReviewList img').length,1);assert.equal(ad.querySelector('[data-event-kind=reviews]').dataset.eventThrough,'3');
  const form=ad.querySelector('[data-review-reply]');form.querySelector('textarea').value='답변을 입력하는 중';form.querySelector('textarea').dispatchEvent(new aw.Event('input',{bubbles:true}));
  let count=adminCalls.length;await aw.reloadAdminReviews();assert.equal(adminCalls.length,count,'background refresh preserves reply drafts');
  form.dispatchEvent(new aw.Event('submit',{bubbles:true,cancelable:true}));await settle();
  const sent=adminCalls.find(x=>x.options.method==='POST');assert.equal(sent.options.body.revision,3);assert.equal(sent.options.body.content,'답변을 입력하는 중');assert.equal(confirms[0].through,3);
  a.dom.window.close();
  for(const name of ['detail','mypage','admin']){
    const html=fs.readFileSync('static/'+name+'.html','utf8'),dom=new JSDOM(html);const ids=[...dom.window.document.querySelectorAll('[id]')].map(x=>x.id);assert.equal(new Set(ids).size,ids.length,name+' duplicate IDs');
    for(const script of dom.window.document.querySelectorAll('script:not([src])'))new Function(script.textContent);
    dom.window.close();
  }
  console.log('PASS: customer write/edit/delete, photo selection/limits/retry/removal, escaped content, admin reply and unread receipts, draft preservation and HTML script parsing');
})().catch(e=>{console.error(e);process.exitCode=1});
