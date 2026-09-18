(function(){
'use strict';
const C=window.ShopCore,E=C.esc,$=id=>document.getElementById(id);
const previewMode=window.parent!==window&&(new URLSearchParams(location.search).get('preview')==='1'||window.name==='allnutrients-preview');
try{C.ensureSeed()}catch(e){console.warn(e.message)}
let config=C.getConfig(),previewProducts=null,cart=C.read(C.KEYS.cart,{}),filters={},sliders=[],toastTimer;
const money=n=>Number(n||0).toLocaleString('ko-KR')+'원';
const products=()=>previewProducts||C.productList();
function toast(msg){const t=$('toast');t.textContent=msg;t.classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>t.classList.remove('show'),2600)}
function imgTag(src,alt,cls='',lazy=true){return `<img src="${E(C.image(src))}" alt="${E(alt)}" class="${cls}" ${lazy?'loading="lazy"':''} decoding="async">`}
function applyTheme(){
 const r=document.documentElement;
 for(const [key,v]of Object.entries({'--brand':config.brandColor,'--ink':config.inkColor,'--bg':config.bgColor,'--product-cols':config.productCols,'--card-radius':config.cardRadius+'px'}))r.style.setProperty(key,v);
 $('topNotice').textContent=config.announcement;$('topNotice').style.background=config.topColor;$('topNotice').hidden=!config.showAnnouncement;
 $('brandName').textContent=config.brandName;$('footerBrandName').textContent=config.brandName;
 $('mainNavigation').innerHTML=config.navigation.filter(m=>m.visible&&C.menuHref(m,config)).map(m=>`<a href="${E(C.menuHref(m,config))}" ${m.kind==='category'?`data-menu-category="${E(m.target)}"`:''}>${E(m.name)}</a>`).join('');
 document.title=config.brandName+' | 과일·채소 주스 전문몰';
}
function productCard(p){
 const unavailable=p.status==='품절'||Number(p.stock)<=0;
 return `<article class="product" data-product-id="${E(p.id)}"><a class="visual" href="detail.html?id=${encodeURIComponent(p.id)}" aria-label="${E(p.name)} 상세보기">${C.image(p.image)?imgTag(p.image,p.name):`<span class="emoji">${E(p.emoji||'🧃')}</span>`}${unavailable?'<span class="sold">품절</span>':''}</a><div class="pbody"><h3>${E(p.name)}</h3><div class="meta">${E(p.capacity||'')} ${p.origin?'· '+E(p.origin):''}</div><div class="desc">${E(p.description||'')}</div><div class="price">${Number(p.compareAt)>Number(p.price)?`<del>${money(p.compareAt)}</del>`:''}<strong>${money(p.price)}</strong></div><div class="product-actions"><a class="btn ghost small" href="detail.html?id=${encodeURIComponent(p.id)}">상세보기</a><button class="btn primary small" data-add-cart="${E(p.id)}" ${unavailable?'disabled':''}>장바구니</button></div></div></article>`;
}
function renderProducts(s){
 let list=products().filter(p=>p.status!=='판매중지');
 if(s.mode==='category')list=list.filter(p=>p.category===s.source);
 if(s.mode==='selected')list=s.productIds.map(id=>list.find(p=>p.id===id)).filter(Boolean);
 if(s.showFilters&&filters[s.id]){const c=config.categories.find(c=>c.id===filters[s.id]&&c.visible);if(c)list=list.filter(p=>p.category===c.source)}
 if(s.limit>0)list=list.slice(0,s.limit);
 return `<section class="page-section" id="${s.id}" data-section-id="${s.id}"><div class="container"><div class="head"><div>${s.eyebrow?`<div class="eyebrow">${E(s.eyebrow)}</div>`:''}<h2>${E(s.title||s.name)}</h2>${s.text?`<p>${E(s.text)}</p>`:''}</div>${s.showFilters?`<div class="filters" aria-label="상품 카테고리"><button class="chip ${!filters[s.id]?'active':''}" data-filter-section="${s.id}" data-category="">전체</button>${config.categories.filter(c=>c.visible).map(c=>`<button class="chip ${filters[s.id]===c.id?'active':''}" data-filter-section="${s.id}" data-category="${c.id}">${E(c.name)}</button>`).join('')}</div>`:''}</div><div class="grid">${list.length?list.map(productCard).join(''):'<div class="empty-section">해당 조건에 등록된 상품이 없습니다.</div>'}</div></div></section>`;
}
function bannerPicture(b){return `<picture>${C.image(b.mobileImage)?`<source media="(max-width:600px)" srcset="${E(b.mobileImage)}">`:''}${imgTag(b.image||b.mobileImage,b.alt||b.name,'',false)}</picture>`}
function renderBanners(s){
 const list=config.banners.filter(b=>b.visible);if(!list.length)return '';
 return `<section class="page-section banner-section" id="${s.id}" data-section-id="${s.id}"><div class="container"><div class="banner-shell" data-slider="${s.id}" role="region" aria-roledescription="슬라이드" aria-label="메인 배너"><div class="banner-slides">${list.map((b,i)=>`<article class="banner-slide ${i===0?'active':''}" data-banner-id="${b.id}" data-slide-index="${i}" ${i!==0?'hidden':''} aria-label="${i+1} / ${list.length}" style="--banner-start:${b.color};--banner-end:${b.endColor}">${b.layout==='image'?`<div class="banner-image-only">${b.href?`<a href="${E(b.href)}">`:''}${C.image(b.image)||C.image(b.mobileImage)?bannerPicture(b):`<div class="banner-fallback">${E(b.title||b.name)}</div>`}${b.href?'</a>':''}</div>`:`<div class="banner-grid"><div class="banner-copy"><div class="eyebrow">${E(b.eyebrow)}</div><${i===0?'h1':'h2'}>${E(b.title)}</${i===0?'h1':'h2'}>${b.text?`<p>${E(b.text)}</p>`:''}${b.button&&b.href?`<a class="btn primary" href="${E(b.href)}">${E(b.button)}</a>`:''}</div><div class="banner-art">${C.image(b.image)||C.image(b.mobileImage)?bannerPicture(b):`<span class="orb o1"></span><span class="orb o2"></span><span class="orb o3"></span><div class="hero-bottle"><div class="hero-label"><small>ALL NUTRIENTS</small>${E(config.brandName)}</div></div>`}</div></div>`}</article>`).join('')}</div>${list.length>1?`<div class="slider-tools"><div class="slide-dots">${list.map((_,i)=>`<button class="${i===0?'active':''}" data-goto="${i}" aria-label="${i+1}번 배너 보기" ${i===0?'aria-current="true"':''}></button>`).join('')}</div><span class="slide-count"><span data-current>01</span> / ${String(list.length).padStart(2,'0')}</span><button data-prev aria-label="이전 배너">‹</button><button data-next aria-label="다음 배너">›</button><button data-pause class="pause">${config.slider.autoplay?'일시정지':'자동재생'}</button></div>`:''}</div></div></section>`;
}
function renderSection(s){
 if(s.type==='banners')return renderBanners(s);
 if(s.type==='products')return renderProducts(s);
 if(s.type==='spacer')return `<section id="${s.id}" data-section-id="${s.id}" class="page-section spacer-section" aria-hidden="true" style="height:${s.height}px"></section>`;
 if(s.type==='image')return `<section id="${s.id}" data-section-id="${s.id}" class="page-section image-section"><div class="container">${s.image?`${s.href?`<a href="${E(s.href)}">`:''}${imgTag(s.image,s.alt,'section-image')}${s.href?'</a>':''}`:(previewMode?'<div class="empty-section">섹션 이미지를 등록해 주세요.</div>':'')}<div class="section-caption">${s.title?`<h2>${E(s.title)}</h2>`:''}${s.text?`<p>${E(s.text)}</p>`:''}${s.button&&s.href?`<a class="btn primary" href="${E(s.href)}">${E(s.button)}</a>`:''}</div></div></section>`;
 return `<section id="${s.id}" data-section-id="${s.id}" class="page-section"><div class="container"><div class="text-section-inner" style="background:${s.bg};color:${s.color};text-align:${s.align}">${s.eyebrow?`<div style="font-size:12px;letter-spacing:.1em;font-weight:800">${E(s.eyebrow)}</div>`:''}${s.title?`<h2>${E(s.title)}</h2>`:''}${s.text?`<p>${E(s.text)}</p>`:''}${s.button&&s.href?`<a class="btn ghost" href="${E(s.href)}">${E(s.button)}</a>`:''}</div></div></section>`;
}
function setupSlider(root){
 const slides=[...root.querySelectorAll('.banner-slide')];if(slides.length<2)return;
 let i=0,timer=null,paused=!config.slider.autoplay||matchMedia('(prefers-reduced-motion:reduce)').matches,hover=false,touchX;
 const dots=[...root.querySelectorAll('[data-goto]')],pause=root.querySelector('[data-pause]');
 function update(n){i=(n+slides.length)%slides.length;slides.forEach((el,j)=>{el.hidden=j!==i;el.classList.toggle('active',j===i)});dots.forEach((el,j)=>{el.classList.toggle('active',j===i);if(j===i)el.setAttribute('aria-current','true');else el.removeAttribute('aria-current')});root.querySelector('[data-current]').textContent=String(i+1).padStart(2,'0');}
 function schedule(){clearInterval(timer);pause.textContent=paused?'자동재생':'일시정지';if(!paused&&!hover&&!document.hidden)timer=setInterval(()=>update(i+1),config.slider.seconds*1000)}
 root.querySelector('[data-prev]').onclick=()=>{update(i-1);schedule()};root.querySelector('[data-next]').onclick=()=>{update(i+1);schedule()};dots.forEach((el,j)=>el.onclick=()=>{update(j);schedule()});pause.onclick=()=>{paused=!paused;schedule()};
 root.onmouseenter=()=>{hover=true;schedule()};root.onmouseleave=()=>{hover=false;schedule()};root.onfocusin=()=>{hover=true;schedule()};root.onfocusout=()=>{hover=false;schedule()};
 root.addEventListener('touchstart',e=>{touchX=e.changedTouches[0].clientX},{passive:true});root.addEventListener('touchend',e=>{const delta=e.changedTouches[0].clientX-touchX;if(Math.abs(delta)>50){update(i+(delta<0?1:-1));schedule()}},{passive:true});
 const visibility=()=>schedule();document.addEventListener('visibilitychange',visibility);schedule();sliders.push(()=>{clearInterval(timer);document.removeEventListener('visibilitychange',visibility)});
}
function renderPage(){
 sliders.forEach(fn=>fn());sliders=[];for(const sid of Object.keys(filters))if(!config.categories.some(c=>c.id===filters[sid]&&c.visible))delete filters[sid];applyTheme();
 $('pageSections').innerHTML=config.sections.filter(s=>s.visible).map(renderSection).join('')||(previewMode?'<div class="empty-section">페이지 섹션을 추가해 주세요.</div>':'');
 document.querySelectorAll('[data-slider]').forEach(setupSlider);renderCart();
}
function saveCart(){C.save(C.KEYS.cart,cart);renderCart()}
function addCart(id){
 if(previewMode)return toast('미리보기에서는 장바구니와 주문을 저장하지 않습니다.');
 const p=products().find(p=>p.id===id);if(!p||p.status!=='판매중'||Number(p.stock)<=0)return toast('현재 구매할 수 없는 상품입니다.');
 if(Number(cart[id]||0)+1>Number(p.stock))return toast('재고 수량을 초과할 수 없습니다.');
 const old=C.clone(cart);cart[id]=Number(cart[id]||0)+1;try{saveCart();toast('장바구니에 담았습니다.')}catch(e){cart=old;toast(e.message)}
}
function changeQty(id,delta){if(delta>0)return addCart(id);const old=C.clone(cart);cart[id]=Math.max(0,Number(cart[id]||0)+delta);if(!cart[id])delete cart[id];try{saveCart()}catch(e){cart=old;toast(e.message)}}
function renderCart(){
 const list=Object.entries(cart||{}).map(([id,q])=>({p:products().find(p=>p.id===id),q:Math.max(0,Number(q)||0)})).filter(x=>x.p&&x.q>0);
 $('cartCount').textContent=list.reduce((t,x)=>t+x.q,0);$('totalPrice').textContent=money(list.reduce((t,x)=>t+x.p.price*x.q,0));
 $('cartList').innerHTML=list.length?list.map(({p,q})=>`<div class="cart-item"><div class="row"><div><strong>${E(p.name)}</strong><div class="meta">${money(p.price)} × ${q}</div></div><strong>${money(p.price*q)}</strong></div><div class="qty"><button data-qty="-1" data-id="${E(p.id)}" aria-label="수량 줄이기">−</button><span>${q}</span><button data-qty="1" data-id="${E(p.id)}" aria-label="수량 늘리기">+</button></div></div>`).join(''):'<div class="empty-section">장바구니가 비어 있습니다.</div>';
}
function openCart(){$('drawer').classList.add('open')};function closeCart(){$('drawer').classList.remove('open')};function closeOrder(){$('orderModal')?.classList.add('open')}
async function openOrder(){if(previewMode)return toast('미리보기에서는 주문하지 않습니다.');if(!Object.keys(cart).length)return toast('장바구니가 비어 있습니다.');closeCart();location.href='checkout.html'}
Object.assign(window,{openCart,closeCart,openOrder,closeOrder,addCart});
$('cartBtn').addEventListener('click',openCart);
document.addEventListener('click',e=>{
 const add=e.target.closest('[data-add-cart]');if(add){addCart(add.dataset.addCart);return}
 const qty=e.target.closest('[data-qty]');if(qty){changeQty(qty.dataset.id,Number(qty.dataset.qty));return}
 const filter=e.target.closest('[data-filter-section]');if(filter){const sid=filter.dataset.filterSection;filters[sid]=filter.dataset.category;const s=config.sections.find(x=>x.id===sid);$(sid).outerHTML=renderProducts(s);return}
 const menu=e.target.closest('[data-menu-category]');if(menu){e.preventDefault();const s=config.sections.find(s=>s.type==='products'&&s.mode==='all'&&s.visible);if(s){filters[s.id]=menu.dataset.menuCategory;$(s.id).outerHTML=renderProducts({...s,showFilters:true});$(s.id).scrollIntoView({behavior:'smooth'})}return}
});
window.addEventListener('storage',e=>{if(previewMode)return;if(!e.key||Object.values(C.KEYS).includes(e.key)){config=C.getConfig();cart=C.read(C.KEYS.cart,{});renderPage()}});
const category=new URLSearchParams(location.search).get('category'),allSection=config.sections.find(s=>s.type==='products'&&s.mode==='all');if(category&&allSection)filters[allSection.id]=category;
renderPage();
})();