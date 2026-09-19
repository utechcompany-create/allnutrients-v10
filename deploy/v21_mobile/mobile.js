(function(){
  'use strict';
  const page=document.body.dataset.shopPage;
  if(!page)return;
  const $=id=>document.getElementById(id),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const icons={home:'<path d="m3 10 9-7 9 7v10H3Z"/><path d="M9 20v-7h6v7"/>',menu:'<path d="M4 6h16M4 12h16M4 18h16"/>',cart:'<path d="M3 3h2l3 13h11l2-9H6"/><circle cx="9" cy="20" r="1"/><circle cx="18" cy="20" r="1"/>',chat:'<path d="M21 11a8 8 0 0 1-8 8H8l-5 3 1-6a8 8 0 1 1 17-5Z"/><path d="M8 10h9M8 13h6"/>',user:'<circle cx="12" cy="8" r="4"/><path d="M4 22v-2a8 8 0 0 1 16 0v2"/>'};
  const icon=name=>`<svg viewBox="0 0 24 24" aria-hidden="true">${icons[name]}</svg>`;
  const nav=document.createElement('nav');nav.className='mobile-bottom-nav';nav.setAttribute('aria-label','모바일 메뉴');
  nav.innerHTML=`<a href="index.html" ${page==='index'?'aria-current="page"':''}>${icon('home')}<span>홈</span></a><button type="button" id="mobileMenuButton" aria-haspopup="dialog" aria-controls="mobileMenu" aria-expanded="false">${icon('menu')}<span>전체메뉴</span></button><a href="index.html?openCart=1" id="mobileCartLink">${icon('cart')}<span>장바구니</span><span id="mobileCartCount" class="mobile-cart-count" hidden></span></a><a href="chat.html" ${page==='chat'?'aria-current="page"':''}>${icon('chat')}<span>상담</span></a><a href="mypage.html" ${['mypage','login','guest-order','return-request'].includes(page)?'aria-current="page"':''}>${icon('user')}<span>마이페이지</span></a>`;
  document.body.append(nav);
  const menu=document.createElement('dialog');menu.id='mobileMenu';menu.className='mobile-menu';menu.setAttribute('aria-labelledby','mobileMenuTitle');
  menu.innerHTML='<div class="mobile-menu-heading"><h2 id="mobileMenuTitle">전체메뉴</h2><button type="button" class="mobile-menu-close" aria-label="메뉴 닫기"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M6 18 18 6"/></svg></button></div><h3>상품 둘러보기</h3><div class="mobile-menu-links" id="mobileCategoryLinks"></div><h3>나의 쇼핑</h3><div class="mobile-menu-links"><a href="mypage.html">마이페이지</a><a href="index.html?openCart=1">장바구니</a><a href="guest-order.html">비회원 주문조회</a><a href="return-request.html">반품·교환 신청</a></div><h3>고객센터</h3><div class="mobile-menu-links"><a href="board.html">고객게시판</a><a href="chat.html">실시간 상담</a><a href="login.html">로그인 · 회원가입</a><a href="admin.html">관리자</a></div>';
  document.body.append(menu);
  const mobile=matchMedia('(max-width:760px)');
  $('mobileMenuButton').onclick=()=>{
    if(!mobile.matches)return;
    const cfg=window.ShopCore?.getConfig();
    const section=cfg?.sections.find(s=>s.visible&&s.type==='products'&&s.mode==='all');
    $('mobileCategoryLinks').innerHTML=`<a href="index.html${section?'#'+encodeURIComponent(section.id):''}">전체상품</a>`+(cfg?.categories||[]).filter(c=>c.visible).map(c=>`<a href="index.html?category=${encodeURIComponent(c.id)}${section?'#'+encodeURIComponent(section.id):''}">${esc(c.name)}</a>`).join('');
    menu.showModal();document.body.classList.add('mobile-menu-open');$('mobileMenuButton').setAttribute('aria-expanded','true');
  };
  menu.querySelector('.mobile-menu-close').onclick=()=>menu.close();
  menu.addEventListener('close',()=>{document.body.classList.remove('mobile-menu-open');$('mobileMenuButton').setAttribute('aria-expanded','false')});
  menu.addEventListener('click',e=>{if(e.target.closest('a'))menu.close()});
  mobile.addEventListener('change',()=>{if(!mobile.matches&&menu.open)menu.close()});
  function updateCount(){
    let cart={};try{cart=JSON.parse(localStorage.getItem('allnutrients-cart-v2')||'{}')}catch(_){}
    const total=Object.values(cart&&typeof cart==='object'?cart:{}).reduce((n,q)=>n+(Number.isFinite(Number(q))?Math.max(0,Math.floor(Number(q))):0),0);
    const badge=$('mobileCartCount');badge.hidden=total===0;badge.textContent=total>99?'99+':String(total);$('mobileCartLink').setAttribute('aria-label',`장바구니, 상품 ${total}개`);
  }
  updateCount();window.addEventListener('storage',updateCount);window.addEventListener('pageshow',updateCount);
  document.addEventListener('click',()=>setTimeout(updateCount,0));
  if($('cartCount'))new MutationObserver(updateCount).observe($('cartCount'),{childList:true,characterData:true,subtree:true});
  $('mobileCartLink').addEventListener('click',e=>{if(page==='index'&&typeof window.openCart==='function'){e.preventDefault();window.openCart()}});
  const drawer=$('drawer');
  if(drawer){
    let wasOpen=false,previousFocus=null;
    drawer.setAttribute('role','dialog');drawer.setAttribute('aria-label','장바구니');
    function syncDrawer(){
      const open=drawer.classList.contains('open');drawer.inert=!open;drawer.setAttribute('aria-hidden',String(!open));document.body.classList.toggle('mobile-cart-open',open);
      if(open){drawer.setAttribute('aria-modal','true');if(!wasOpen){previousFocus=document.activeElement;drawer.querySelector('button')?.focus()}}
      else{drawer.removeAttribute('aria-modal');if(wasOpen)previousFocus?.focus()}
      wasOpen=open;
    }
    new MutationObserver(syncDrawer).observe(drawer,{attributes:true,attributeFilter:['class']});syncDrawer();
    drawer.addEventListener('keydown',e=>{
      if(e.key==='Escape'){e.preventDefault();window.closeCart();return}
      if(e.key!=='Tab')return;
      const nodes=[...drawer.querySelectorAll('button:not(:disabled),a[href],input:not(:disabled)')].filter(el=>el.getClientRects().length);
      if(!nodes.length)return;
      if(e.shiftKey&&document.activeElement===nodes[0]){e.preventDefault();nodes.at(-1).focus()}
      else if(!e.shiftKey&&document.activeElement===nodes.at(-1)){e.preventDefault();nodes[0].focus()}
    });
    const params=new URLSearchParams(location.search);
    if(params.get('openCart')==='1'&&!params.has('preview')&&typeof window.openCart==='function'){
      window.openCart();params.delete('openCart');const query=params.toString();history.replaceState(history.state,'',location.pathname+(query?'?'+query:'')+location.hash);
    }
  }
  function editing(){const el=document.activeElement;document.body.classList.toggle('mobile-editing',Boolean(el?.matches('textarea,input:not([type=checkbox]):not([type=radio]):not([type=button]):not([readonly])')))}
  document.addEventListener('focusin',editing);document.addEventListener('focusout',()=>setTimeout(editing,0));
  // Label dynamically loaded order cells without duplicating private order data.
  document.querySelectorAll('main table').forEach(table=>{
    const headers=[...table.querySelectorAll('thead th')].map(el=>el.textContent.trim());if(!headers.length)return;
    table.classList.add('mobile-card-table');
    const body=table.querySelector('tbody');if(!body)return;
    const label=()=>body.querySelectorAll('tr').forEach(row=>[...row.children].forEach((cell,i)=>{
      cell.dataset.mobileLabel=headers[i]||'';
      if(!cell.querySelector('.mobile-cell-value')){const value=document.createElement('div');value.className='mobile-cell-value';while(cell.firstChild)value.append(cell.firstChild);cell.append(value)}
    }));
    label();new MutationObserver(label).observe(body,{childList:true,subtree:true});
  });
  if($('total')&&$('mobilePayTotal')){
    const sync=()=>{$('mobilePayTotal').textContent=$('total').textContent};sync();new MutationObserver(sync).observe($('total'),{childList:true,characterData:true,subtree:true});
  }
  // Mobile keyboards and browser autofill use the same existing form controls.
  const hints={customerName:['name','text'],name:['name','text'],customerPhone:['tel','tel'],phone:['tel','tel'],customerEmail:['email','email'],email:['email','email'],postcode:['postal-code','numeric'],address1:['address-line1','text'],address2:['address-line2','text']};
  document.querySelectorAll('input[name]').forEach(input=>{
    const hint=hints[input.name];if(hint){input.autocomplete=hint[0];input.inputMode=hint[1]}
    if(input.type==='password')input.autocomplete=(input.closest('#registerForm')||/new|confirm/i.test(input.name))?'new-password':'current-password';
  });
  if(['payment-success','payment-fail'].includes(page)){
    const notice=sessionStorage.getItem('shipping_address_notice');
    if(notice){const p=document.createElement('p');p.className='notice';p.textContent=notice;document.querySelector('main .wrap')?.append(p);sessionStorage.removeItem('shipping_address_notice')}
  }
})();
