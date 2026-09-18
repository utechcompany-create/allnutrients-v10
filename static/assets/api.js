(function(){
  function cookie(name){return document.cookie.split('; ').find(x=>x.startsWith(name+'='))?.split('=').slice(1).join('=')||''}
  async function api(url,options={}){
    const o={credentials:'same-origin',...options};o.headers={...(o.headers||{})};
    if(o.body && !(o.body instanceof FormData) && typeof o.body!=='string'){o.headers['Content-Type']='application/json';o.body=JSON.stringify(o.body)}
    if(!['GET','HEAD','OPTIONS'].includes((o.method||'GET').toUpperCase()))o.headers['x-csrf-token']=decodeURIComponent(cookie('allnutrients_csrf'));
    const r=await fetch(url,o);let data=null;try{data=await r.json()}catch(_){}
    if(!r.ok)throw new Error(data?.detail||data?.message||('요청 실패 '+r.status));
    return data;
  }
  function money(n){return Number(n||0).toLocaleString('ko-KR')+'원'}
  function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
  window.AppAPI={api,money,esc,cookie};
})();