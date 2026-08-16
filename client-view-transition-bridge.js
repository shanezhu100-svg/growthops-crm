(()=>{
  'use strict';
  const vm=window.__growthOpsVm;
  if(!vm)return;
  const VERSION='client-view-transition-v20-soft-detail-entry';
  const STYLE_ID='growthops-client-view-transition-style';
  const SURFACE_CLASS='growthops-client-nav-surface';
  const EXIT_CLASS='growthops-client-nav-exit';
  const ENTER_CLASS='growthops-client-nav-enter';
  const ACTIVE_CLASS='growthops-client-nav-enter-active';
  const reduceMotion=window.matchMedia?.('(prefers-reduced-motion: reduce)');
  let lastSurface=null;
  let lastActivationAt=0;
  let cleanupTimer=0;

  const text=el=>String(el?.textContent||'').replace(/\s+/g,' ').trim();
  const isClientDetailOpenButton=button=>{
    if(!button)return false;
    const label=text(button);
    if(label==='详情'||label==='查看客户详情')return true;
    const row=button.closest('tbody tr');
    return !!row&&button===row.querySelector('td:first-child button');
  };
  const resolveSurface=hint=>{
    if(hint instanceof Element&&hint.isConnected){
      const main=hint.closest?.('main');
      if(main)return main;
    }
    if(lastSurface?.isConnected)return lastSurface;
    return document.querySelector('main,[role="main"]')||document.body;
  };
  const installStyle=()=>{
    if(document.getElementById(STYLE_ID))return;
    const style=document.createElement('style');
    style.id=STYLE_ID;
    style.textContent=`
.${SURFACE_CLASS}{will-change:opacity,transform;transform-origin:50% 0}
.${SURFACE_CLASS}.${EXIT_CLASS}{opacity:.88;transform:translateY(-2px) scale(.999);transition:opacity 90ms cubic-bezier(.4,0,1,1),transform 120ms cubic-bezier(.4,0,1,1)}
.${SURFACE_CLASS}.${ENTER_CLASS}{opacity:.84;transform:translateY(7px) scale(.999);transition:none!important}
.${SURFACE_CLASS}.${ACTIVE_CLASS}{opacity:1;transform:translateY(0) scale(1);transition:opacity 180ms cubic-bezier(.16,1,.3,1),transform 220ms cubic-bezier(.16,1,.3,1)}
@media (prefers-reduced-motion: reduce){
  .${SURFACE_CLASS}.${EXIT_CLASS},.${SURFACE_CLASS}.${ENTER_CLASS},.${SURFACE_CLASS}.${ACTIVE_CLASS}{opacity:1;transform:none;transition:none!important}
}`;
    document.head.appendChild(style);
  };
  const clearClasses=surface=>{
    if(!(surface instanceof Element))return;
    surface.classList.remove(EXIT_CLASS,ENTER_CLASS,ACTIVE_CLASS,SURFACE_CLASS);
  };
  const armExit=surface=>{
    if(reduceMotion?.matches)return;
    surface=resolveSurface(surface);
    if(!(surface instanceof Element))return;
    if(cleanupTimer)clearTimeout(cleanupTimer);
    clearClasses(surface);
    surface.classList.add(SURFACE_CLASS,EXIT_CLASS);
    cleanupTimer=setTimeout(()=>clearClasses(surface),420);
  };
  const playEnter=()=>{
    if(reduceMotion?.matches)return;
    const surface=resolveSurface();
    if(!(surface instanceof Element))return;
    if(cleanupTimer)clearTimeout(cleanupTimer);
    clearClasses(surface);
    surface.classList.add(SURFACE_CLASS,ENTER_CLASS);
    void surface.offsetHeight;
    requestAnimationFrame(()=>{
      requestAnimationFrame(()=>{
        if(vm.currentPage!=='client-detail'){clearClasses(surface);return}
        surface.classList.remove(ENTER_CLASS);
        surface.classList.add(ACTIVE_CLASS);
        cleanupTimer=setTimeout(()=>clearClasses(surface),260);
      });
    });
  };
  const scheduleEnter=()=>{
    const run=()=>requestAnimationFrame(playEnter);
    if(typeof vm.$nextTick==='function')vm.$nextTick(run);
    else queueMicrotask(run);
  };

  installStyle();
  window.addEventListener('pointerdown',event=>{
    if(vm.currentPage!=='clients')return;
    const button=event.target?.closest?.('button');
    if(!isClientDetailOpenButton(button))return;
    lastSurface=resolveSurface(button);
    lastActivationAt=Date.now();
    armExit(lastSurface);
  },true);

  const originalOpenClientDetail=vm.openClientDetail;
  if(typeof originalOpenClientDetail==='function'){
    vm.openClientDetail=function(...args){
      const fromClients=vm.currentPage==='clients';
      const userActivated=Date.now()-lastActivationAt<1000;
      if(!fromClients||!userActivated||reduceMotion?.matches)return originalOpenClientDetail.apply(this,args);
      let result;
      try{result=originalOpenClientDetail.apply(this,args)}
      catch(error){clearClasses(resolveSurface());throw error}
      scheduleEnter();
      return result;
    };
  }

  window.__GROWTHOPS_CLIENT_VIEW_TRANSITION__={
    installed:true,
    version:VERSION,
    playEnter,
    getSurface:()=>resolveSurface()
  };
})();