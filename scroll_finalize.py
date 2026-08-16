from pathlib import Path
import hashlib

root = Path(__file__).resolve().parent
dist = root / 'dist'
index_path = dist / 'index.html'
html = index_path.read_text(encoding='utf-8')

security_tag = '<script src="/cloud-security-hotfix.js"></script>'
script_id = 'growthops-client-scroll-state'
if html.count(security_tag) != 1:
    raise SystemExit('Unexpected security hotfix script tag count before scroll finalize')
if script_id in html:
    raise SystemExit('Client scroll state script already present before finalize')

scroll_script = r'''<script id="growthops-client-scroll-state">
(()=>{
  'use strict';

  const vm=window.__growthOpsVm;
  if(!vm||typeof vm.$watch!=='function')return;

  const STORAGE_KEY='growthops_client_scroll_state_v1';
  const readState=()=>{
    try{
      const raw=JSON.parse(sessionStorage.getItem(STORAGE_KEY)||'{}');
      return {
        clients:Number.isFinite(Number(raw.clients))?Math.max(0,Number(raw.clients)):0,
        details:raw.details&&typeof raw.details==='object'&&!Array.isArray(raw.details)?raw.details:{},
        detailFallback:Number.isFinite(Number(raw.detailFallback))?Math.max(0,Number(raw.detailFallback)):0
      };
    }catch{
      return {clients:0,details:{},detailFallback:0};
    }
  };
  const state=readState();
  const persistState=()=>{try{sessionStorage.setItem(STORAGE_KEY,JSON.stringify(state))}catch{}};
  const currentClientKey=()=>String(vm.selectedClientId??vm.selectedClient?.id??'');
  const currentY=()=>Math.max(0,Math.round(window.scrollY||window.pageYOffset||0));

  let currentPage=String(vm.currentPage||'');
  let scrollRaf=0;

  function savePosition(pageName,y=currentY()){
    if(pageName==='clients'){
      state.clients=y;
    }else if(pageName==='client-detail'){
      const clientKey=currentClientKey();
      if(clientKey)state.details[clientKey]=y;
      else state.detailFallback=y;
    }
    persistState();
  }

  function restorePosition(y){
    const target=Math.max(0,Number(y)||0);
    const apply=()=>window.scrollTo({top:target,left:0,behavior:'auto'});
    const staged=()=>{
      apply();
      requestAnimationFrame(()=>{
        apply();
        setTimeout(apply,60);
        setTimeout(apply,180);
      });
    };
    if(typeof vm.$nextTick==='function')vm.$nextTick(()=>requestAnimationFrame(staged));
    else requestAnimationFrame(staged);
  }

  if('scrollRestoration' in history)history.scrollRestoration='manual';

  window.addEventListener('scroll',()=>{
    if(scrollRaf)cancelAnimationFrame(scrollRaf);
    scrollRaf=requestAnimationFrame(()=>{
      scrollRaf=0;
      savePosition(currentPage);
    });
  },{passive:true});

  vm.$watch('currentPage',(next,prev)=>{
    const from=String(prev||currentPage||'');
    const to=String(next||'');

    // Capture the old page before Vue swaps the DOM. This is the list position the
    // user actually clicked from, not the scroll position of the newly rendered page.
    savePosition(from);
    currentPage=to;

    // Entering a client from the list is a new detail view: never inherit the list Y.
    if(from==='clients'&&to==='client-detail'){
      restorePosition(0);
      return;
    }

    // The detail back button must return to the exact list scroll position.
    if(from==='client-detail'&&to==='clients'){
      restorePosition(state.clients);
      return;
    }

    // Keep detail-page scroll independent for non-list transitions (for example,
    // returning from an edit/form sub-view). It never overwrites the clients value.
    if(to==='client-detail'&&from!=='clients'){
      const clientKey=currentClientKey();
      const saved=clientKey&&Number.isFinite(Number(state.details[clientKey]))
        ?Number(state.details[clientKey])
        :state.detailFallback;
      restorePosition(saved);
    }
  },{flush:'sync'});

  window.addEventListener('beforeunload',()=>savePosition(currentPage));

  window.__GROWTHOPS_CLIENT_SCROLL_STATE__={
    installed:true,
    version:'clients-detail-isolated-v1',
    storageKey:STORAGE_KEY
  };
})();
</script>'''

html = html.replace(security_tag, security_tag + scroll_script, 1)
index_path.write_text(html, encoding='utf-8')

print(
    'SCROLL_FINALIZE_OK: '
    f'index={hashlib.sha256(index_path.read_bytes()).hexdigest()}'
)
