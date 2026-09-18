/* Shared schema, v5 migration and safe rendering helpers. No external dependency. */
(function () {
  'use strict';
  const KEYS = { design:'allnutrients-design-v1', products:'allnutrients-products-v2', cart:'allnutrients-cart-v2', orders:'allnutrients-orders-v2' };
  const SEED = [{"id": "P1001", "code": "RFC-COCO-1000", "name": "RFC 코코넛워터", "category": "코코넛워터", "price": 15900, "compareAt": 18900, "stock": 120, "status": "판매중", "origin": "베트남", "capacity": "1L", "description": "깔끔하고 시원하게 즐기는 데일리 코코넛워터", "emoji": "🥥", "image": ""}, {"id": "P1002", "code": "TANDO-GINGER-99", "name": "탄도 생강즙 99%", "category": "채소·뿌리", "price": 21900, "compareAt": 24900, "stock": 80, "status": "판매중", "origin": "베트남", "capacity": "제품별 상이", "description": "생강의 알싸하고 깊은 풍미를 담은 진한 한 병", "emoji": "🫚", "image": ""}, {"id": "P1003", "code": "RFC-NONI", "name": "RFC 노니주스", "category": "과일주스", "price": 26900, "compareAt": 29900, "stock": 65, "status": "판매중", "origin": "베트남", "capacity": "제품별 상이", "description": "노니 특유의 진한 풍미를 간편하게 즐기는 주스", "emoji": "🍐", "image": ""}, {"id": "P1004", "code": "CABBAGE-JUICE", "name": "양배추즙", "category": "채소·뿌리", "price": 18900, "compareAt": 21900, "stock": 40, "status": "판매중", "origin": "베트남", "capacity": "제품별 상이", "description": "부담 없이 매일 챙겨 마시기 좋은 채소 주스", "emoji": "🥬", "image": ""}];
  const BASE = {
    brandName:'올영양소', announcement:'올영양소 공식몰 · 5만원 이상 무료배송',
    heroEyebrow:'ALL NUTRIENTS', heroTitle:'매일 한 병,\n영양을 더 쉽게.',
    heroText:'과일과 채소의 맛을 일상 속에서 간편하게. 올영양소의 주스 컬렉션을 만나보세요.',
    heroButton:'상품 보러가기', heroImage:'', shopEyebrow:'SHOP', shopTitle:'오늘의 영양 한 병',
    shopText:'원하는 맛과 라이프스타일에 맞춰 골라보세요.',
    storyTitle:'필요한 영양을 복잡하지 않게.',
    storyText:'올영양소는 과일·채소·뿌리 원료 기반 음료를 한곳에서 편하게 고를 수 있는 전문몰을 지향합니다.',
    brandColor:'#2f7d4e', inkColor:'#183226', bgColor:'#f6f8f4', topColor:'#173126',
    heroStart:'#dcefbf', heroEnd:'#f4f8df', storyColor:'#173126', productCols:4, cardRadius:22,
    showAnnouncement:true, showHero:true, showFilters:true, showStory:true
  };
  const clone = x => JSON.parse(JSON.stringify(x));
  const text = (x,f='') => typeof x === 'string' ? x : f;
  const id = prefix => prefix + '-' + (globalThis.crypto?.randomUUID?.() || Date.now().toString(36)+'-'+Math.random().toString(36).slice(2,9));
  const esc = x => String(x ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const hex = (v,f) => /^#[\da-f]{6}$/i.test(v||'') ? v : f;
  const number = (v,min,max,f) => Number.isFinite(Number(v)) ? Math.max(min,Math.min(max,Math.round(Number(v)))) : f;
  function read(key, fallback) {
    try { const v=localStorage.getItem(key); return v===null ? clone(fallback) : JSON.parse(v); }
    catch(e) { console.warn('저장 데이터를 읽을 수 없습니다:',key,e); return clone(fallback); }
  }
  function save(key, value) {
    try { localStorage.setItem(key,JSON.stringify(value)); }
    catch(e) { throw new Error('저장하지 못했습니다. 브라우저 저장 공간이나 접근 권한을 확인하세요. 이미지 수·크기를 줄이거나 디자인 백업 후 다시 시도해 주세요.'); }
  }
  function url(v) {
    const s=String(v||'').trim();
    if (!s) return '';
    if (/^https?:\/\//i.test(s)) { try { const u=new URL(s); return ['http:','https:'].includes(u.protocol)?u.href:''; } catch(_) { return ''; } }
    if (/^#[\w-]+$/.test(s)) return s;
    if (/^(?:index|detail|board|admin)\.html(?:[?#][^\s<>"'\`\\]*)?$/.test(s)) return s;
    return '';
  }
  function image(v) {
    const s=String(v||'').trim();
    if (/^data:image\/(?:png|jpe?g|webp|gif);base64,[a-z\d+/=\s]+$/i.test(s)) return s;
    if (/^\/uploads\/[a-zA-Z0-9._-]+$/.test(s)) return s;
    return /^https?:\/\//i.test(s) ? url(s) : '';
  }
  function productList() { const p=read(KEYS.products,SEED); return Array.isArray(p)?p:clone(SEED); }
  function ensureSeed() { if(localStorage.getItem(KEYS.products)===null) save(KEYS.products,SEED); }
  function unique(list,prefix,fix) {
    const seen=new Set();
    return list.filter(x=>x && typeof x==='object').map(x=>{
      const n=fix(x); let k=text(x.id);
      if(!/^[a-zA-Z0-9_-]+$/.test(k)||seen.has(k)) k=id(prefix);
      n.id=k;seen.add(k); return n;
    });
  }
  function normalize(raw, products=productList()) {
    const r=raw&&typeof raw==='object'&&!Array.isArray(raw)?raw:{};
    const d={...BASE};
    for(const k of Object.keys(BASE)) if(k in r) d[k]=typeof BASE[k]==='boolean'?r[k]!==false:typeof BASE[k]==='number'?Number(r[k]):text(r[k],BASE[k]);
    for(const k of ['brandColor','inkColor','bgColor','topColor','heroStart','heroEnd','storyColor']) d[k]=hex(d[k],BASE[k]);
    d.brandName=d.brandName.trim()||BASE.brandName;
    d.productCols=number(d.productCols,2,5,4);d.cardRadius=number(d.cardRadius,0,40,22);
    d.heroImage=image(d.heroImage);d.version=6;
    d.slider={autoplay:r.slider?.autoplay!==false,seconds:number(r.slider?.seconds??5,3,15,5)};
    d.banners=unique((Array.isArray(r.banners)?r.banners:[{
      id:'banner-main',name:'메인 배너',eyebrow:d.heroEyebrow,title:d.heroTitle,text:d.heroText,
      button:d.heroButton,href:'#products',image:d.heroImage,visible:true
    }]).slice(0,20),'banner',b=>({
      name:text(b.name,'새 배너'),eyebrow:text(b.eyebrow),title:text(b.title),text:text(b.text),button:text(b.button),
      href:url(b.href),image:image(b.image),mobileImage:image(b.mobileImage),alt:text(b.alt,b.name||'메인 배너'),
      visible:b.visible!==false,layout:b.layout==='image'?'image':'split',
      color:hex(b.color,d.heroStart),endColor:hex(b.endColor,d.heroEnd)
    }));
    const existingCats=[...new Set(products.map(p=>text(p.category)).filter(Boolean))];
    d.categories=unique((Array.isArray(r.categories)?r.categories:existingCats.map((c,i)=>({id:'cat-'+(i+1),name:c,source:c,visible:true}))).slice(0,30),'cat',c=>({name:text(c.name,'새 카테고리'),source:text(c.source,c.name||'기타'),visible:c.visible!==false}));
    const initial=[
      {id:'hero',type:'banners',name:'메인 배너',visible:d.showHero},
      {id:'products',type:'products',name:'전체상품',eyebrow:d.shopEyebrow,title:d.shopTitle,text:d.shopText,showFilters:d.showFilters,mode:'all',visible:true},
      {id:'best',type:'products',name:'베스트 · 추천상품',eyebrow:'OUR PICKS',title:'함께 만나보는 추천 상품',text:'마음에 드는 한 병을 골라보세요.',mode:'selected',productIds:products.slice(0,4).map(p=>p.id),visible:true},
      {id:'story',type:'text',name:'브랜드스토리',eyebrow:'OUR STORY',title:d.storyTitle,text:d.storyText,bg:d.storyColor,color:'#ffffff',visible:d.showStory}
    ];
    const types=['banners','products','text','image','spacer'];
    d.sections=unique((Array.isArray(r.sections)?r.sections:initial).slice(0,30),'section',s=>({
      type:types.includes(s.type)?s.type:'text',name:text(s.name,'새 섹션'),visible:s.visible!==false,
      eyebrow:text(s.eyebrow),title:text(s.title),text:text(s.text),button:text(s.button),href:url(s.href),
      image:image(s.image),alt:text(s.alt,s.title||'섹션 이미지'),bg:hex(s.bg,'#ffffff'),color:hex(s.color,d.inkColor),
      align:s.align==='center'?'center':'left',showFilters:s.showFilters===true,
      mode:['all','category','selected'].includes(s.mode)?s.mode:'all',source:text(s.source),
      productIds:Array.isArray(s.productIds)?s.productIds.filter(x=>typeof x==='string'):[],
      limit:number(s.limit??0,0,40,0),height:number(s.height??48,8,240,48)
    }));
    d.navigation=unique((Array.isArray(r.navigation)?r.navigation:[
      {id:'menu-all',name:'전체상품',kind:'section',target:'products'},
      {id:'menu-best',name:'베스트',kind:'section',target:'best'},
      {id:'menu-brand',name:'브랜드',kind:'section',target:'story'},
      {id:'menu-board',name:'고객게시판',kind:'page',target:'board.html'}
    ]).slice(0,12),'menu',m=>({name:text(m.name,'새 메뉴'),kind:['section','category','page','url'].includes(m.kind)?m.kind:'section',target:text(m.target),visible:m.visible!==false}));
    d.savedAt=text(r.savedAt);return d;
  }
  function getConfig() { return normalize(read(KEYS.design,{})); }
  function legacy(d) {
    const b=d.banners[0],s=d.sections.find(x=>x.id==='products')||d.sections.find(x=>x.type==='products'),story=d.sections.find(x=>x.id==='story');
    if(b) Object.assign(d,{heroTitle:b.title,heroText:b.text,heroButton:b.button,heroImage:b.image,heroEyebrow:b.eyebrow});
    if(s)Object.assign(d,{shopTitle:s.title,shopText:s.text,shopEyebrow:s.eyebrow,showFilters:s.showFilters});
    if(story)Object.assign(d,{storyTitle:story.title,storyText:story.text,storyColor:story.bg});
    d.showHero=d.sections.some(x=>x.type==='banners'&&x.visible);d.showStory=!!story?.visible; return d;
  }
  function menuHref(m,d) {
    if(m.kind==='section')return d.sections.some(s=>s.id===m.target&&s.visible)?'#'+m.target:'';
    if(m.kind==='category') {
      const c=d.categories.find(c=>c.id===m.target&&c.visible),s=d.sections.find(s=>s.type==='products'&&s.mode==='all'&&s.visible);
      return c&&s?'index.html?category='+encodeURIComponent(c.id)+'#'+s.id:'';
    }
    return url(m.target);
  }
  async function compress(file,maxWidth=1800) {
    if(!/^image\/(jpeg|png|webp|gif)$/.test(file.type))throw new Error('JPG, PNG, WebP, GIF 이미지 파일을 선택해 주세요.');
    if(file.size>15*1024*1024)throw new Error('이미지는 파일당 15MB 이하로 준비해 주세요.');
    const blobURL=URL.createObjectURL(file);
    try {
      const im=await new Promise((res,rej)=>{const im=new Image();im.onload=()=>res(im);im.onerror=()=>rej(new Error('이미지를 읽을 수 없습니다.'));im.src=blobURL;});
      const scale=Math.min(1,maxWidth/im.width,3200/im.height,Math.sqrt(5800000/(im.width*im.height)));
      const canvas=document.createElement('canvas');canvas.width=Math.max(1,Math.round(im.width*scale));canvas.height=Math.max(1,Math.round(im.height*scale));
      const ctx=canvas.getContext('2d');ctx.fillStyle='#ffffff';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.drawImage(im,0,0,canvas.width,canvas.height);
      let result=canvas.toDataURL('image/jpeg',.82);
      if(result.length>850000)result=canvas.toDataURL('image/jpeg',.60);
      if(result.length>1500000)throw new Error('압축 후에도 이미지가 너무 큽니다. 더 작은 이미지를 선택해 주세요.');
      return result;
    } finally {URL.revokeObjectURL(blobURL);}
  }
  window.ShopCore={KEYS,SEED,BASE,clone,id,esc,hex,url,image,read,save,productList,ensureSeed,normalize,getConfig,legacy,menuHref,compress};
})();