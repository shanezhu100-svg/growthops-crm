(()=>{
  'use strict';
  const vm=window.__growthOpsVm;
  if(!vm)return;
  const BOUND='data-growthops-native-action';
  const TOKEN_KEY='growthops_crm_token_v2';
  const PAGE_SCROLL_PAGES=new Set(['clients','client-form','client-detail']);
  const pageScrollPositions=Object.create(null);
  const pageScrollTargets=Object.create(null);
  let pendingClientCloudSaves=0;
  let routeSwitching=false;
  let lastObservedPage=vm.currentPage||'';
  let lastClientPointerTarget=null;
  try{if('scrollRestoration' in window.history)window.history.scrollRestoration='manual'}catch{}
  const text=el=>String(el?.textContent||'').replace(/\s+/g,' ').trim();
  const bind=(el,key,handler)=>{
    if(!el||el.getAttribute(BOUND)===key)return;
    el.setAttribute(BOUND,key);
    el.addEventListener('click',event=>{
      event.preventDefault();
      event.stopImmediatePropagation();
      try{handler(el,event)}catch(e){console.error(e);vm.notify?.('操作执行失败，请刷新页面后重试')}
    },true);
  };
  const validateButtonForm=button=>{
    const form=button?.closest('form');
    return !form||typeof form.reportValidity!=='function'||form.reportValidity();
  };
  const clearSessionRestoreCover=()=>{
    const hasToken=!!localStorage.getItem(TOKEN_KEY);
    if(vm.currentUser||!hasToken)document.documentElement.classList.remove('growthops-session-restoring');
  };
  const closeState=(key,root)=>{
    vm[key]=false;
    try{vm.$forceUpdate?.()}catch{}
    requestAnimationFrame(()=>{if(vm[key]===false&&root?.isConnected)root.remove()});
  };
  const bindModal=(root,stateKey,saveLabel,saveMethod)=>{
    if(!root)return;
    root.querySelectorAll('button').forEach(button=>{
      const label=text(button);
      if(label==='取消'||button.title==='关闭')bind(button,`${stateKey}-close`,()=>closeState(stateKey,root));
      if(saveLabel(label))bind(button,`${stateKey}-save`,()=>{
        if(!validateButtonForm(button))return;
        if(typeof vm[saveMethod]!=='function'){vm.notify?.('保存功能未加载，请刷新页面');return}
        const result=vm[saveMethod]();
        if(result&&typeof result.catch==='function')result.catch(error=>{console.error(error);vm.notify?.('保存失败，请稍后重试')});
        requestAnimationFrame(()=>{if(vm[stateKey]===false&&root.isConnected)root.remove()});
      });
    });
  };
  const setPageUrl=page=>{
    try{
      const next=new URL(window.location.href);
      next.hash=page;
      window.history.replaceState(window.history.state,'',next.toString());
    }catch{}
  };
  const documentScroller=()=>document.scrollingElement||document.documentElement||document.body;
  const normalizeScrollTarget=target=>{
    if(target===window||target===document||target===document.documentElement||target===document.body)return documentScroller();
    return target instanceof Element?target:null;
  };
  const hasVerticalRange=target=>!!target&&Number(target.scrollHeight||0)>Number(target.clientHeight||0)+1;
  const canOwnVerticalScroll=target=>{
    target=normalizeScrollTarget(target);
    if(!target||!hasVerticalRange(target))return false;
    if(target===documentScroller())return true;
    try{
      const overflowY=getComputedStyle(target).overflowY;
      return overflowY!=='visible'&&overflowY!=='clip';
    }catch{return true}
  };
  const findScrollTarget=node=>{
    let current=node instanceof Element?node:null;
    while(current&&current!==document.body&&current!==document.documentElement){
      if(canOwnVerticalScroll(current))return current;
      current=current.parentElement;
    }
    return documentScroller();
  };
  const scanVisibleScrollTarget=()=>{
    const doc=documentScroller();
    let best=canOwnVerticalScroll(doc)?doc:null;
    let bestScore=best?Math.max(0,Number(best.scrollHeight||0)-Number(best.clientHeight||0)):0;
    let candidates=[];
    try{candidates=[...document.querySelectorAll('main,[class*="overflow-y-auto"],[class*="overflow-auto"],[class*="overflow-y-scroll"],[style*="overflow"]')]}catch{}
    for(const el of candidates){
      if(!canOwnVerticalScroll(el))continue;
      let rect;
      try{rect=el.getBoundingClientRect()}catch{continue}
      if(rect.width<20||rect.height<20||rect.bottom<=0||rect.top>=window.innerHeight)continue;
      const score=Math.max(0,Number(el.scrollHeight||0)-Number(el.clientHeight||0))+Math.min(rect.height,window.innerHeight);
      if(score>bestScore){best=el;bestScore=score}
    }
    return best||doc;
  };
  const resolvePageScrollTarget=(page,hint)=>{
    const hinted=hint instanceof Element?findScrollTarget(hint):normalizeScrollTarget(hint);
    if(hinted&&hinted.isConnected!==false){pageScrollTargets[page]=hinted;return hinted}
    const saved=normalizeScrollTarget(pageScrollTargets[page]);
    if(saved&&saved.isConnected!==false)return saved;
    const detected=scanVisibleScrollTarget();
    if(detected)pageScrollTargets[page]=detected;
    return detected;
  };
  const readTargetScrollTop=target=>Math.max(0,Number(normalizeScrollTarget(target)?.scrollTop||0));
  const writeTargetScrollTop=(target,top)=>{
    target=normalizeScrollTarget(target);
    if(!target)return;
    const value=Math.max(0,Number(top)||0);
    target.scrollTop=value;
    if(target===documentScroller()){
      if(document.documentElement&&document.documentElement!==target)document.documentElement.scrollTop=value;
      if(document.body&&document.body!==target)document.body.scrollTop=value;
    }
  };
  const rememberPageScroll=(page=vm.currentPage,hint)=>{
    if(routeSwitching||!PAGE_SCROLL_PAGES.has(page))return;
    const target=resolvePageScrollTarget(page,hint);
    if(!target)return;
    pageScrollTargets[page]=target;
    pageScrollPositions[page]=readTargetScrollTop(target);
  };
  const getPageScroll=page=>{
    const value=pageScrollPositions[page];
    return Number.isFinite(value)?Math.max(0,value):0;
  };
  const applyPageScroll=(page,top,hint)=>{
    const target=resolvePageScrollTarget(page,hint);
    writeTargetScrollTop(target,top);
    return target;
  };
  const restorePageScrollInstant=(page,hint)=>{
    const targetTop=getPageScroll(page);
    const root=document.documentElement;
    const body=document.body;
    const oldRootBehavior=root.style.scrollBehavior;
    const oldBodyBehavior=body?.style?.scrollBehavior||'';
    routeSwitching=true;
    root.style.scrollBehavior='auto';
    if(body)body.style.scrollBehavior='auto';
    const apply=()=>applyPageScroll(page,targetTop,hint);
    const saved=normalizeScrollTarget(pageScrollTargets[page]);
    if(saved&&saved.isConnected!==false)apply();
    const finish=()=>{
      apply();
      routeSwitching=false;
      lastObservedPage=page;
      root.style.scrollBehavior=oldRootBehavior;
      if(body)body.style.scrollBehavior=oldBodyBehavior;
    };
    const settle=()=>{
      apply();
      requestAnimationFrame(()=>{
        apply();
        setTimeout(finish,90);
      });
    };
    if(typeof vm.$nextTick==='function')vm.$nextTick(settle);
    else queueMicrotask(settle);
  };
  const navigateWithPageScroll=(page,sourceHint)=>{
    const sourcePage=vm.currentPage;
    if(sourcePage)rememberPageScroll(sourcePage,sourceHint);
    const targetTop=getPageScroll(page);
    const root=document.documentElement;
    const body=document.body;
    const oldRootBehavior=root.style.scrollBehavior;
    const oldBodyBehavior=body?.style?.scrollBehavior||'';
    routeSwitching=true;
    root.style.scrollBehavior='auto';
    if(body)body.style.scrollBehavior='auto';
    vm.currentPage=page;
    vm.mobileMenuOpen=false;
    setPageUrl(page);
    const savedTarget=normalizeScrollTarget(pageScrollTargets[page]);
    if(savedTarget&&savedTarget.isConnected!==false)writeTargetScrollTop(savedTarget,targetTop);
    try{vm.$forceUpdate?.()}catch{}
    const settle=()=>{
      if(vm.currentPage!==page){
        vm.currentPage=page;
        try{vm.$forceUpdate?.()}catch{}
      }
      applyPageScroll(page,targetTop);
      requestAnimationFrame(()=>{
        applyPageScroll(page,targetTop);
        setTimeout(()=>{
          applyPageScroll(page,targetTop);
          routeSwitching=false;
          lastObservedPage=page;
          root.style.scrollBehavior=oldRootBehavior;
          if(body)body.style.scrollBehavior=oldBodyBehavior;
        },90);
      });
    };
    if(typeof vm.$nextTick==='function')vm.$nextTick(settle);
    else queueMicrotask(settle);
  };
  const finalizeClientListNavigation=()=>navigateWithPageScroll('clients');
  const protectPendingSave=event=>{
    if(pendingClientCloudSaves<=0)return;
    event.preventDefault();
    event.returnValue='';
  };
  const trackClientCloudSave=promise=>{
    pendingClientCloudSaves+=1;
    window.addEventListener('beforeunload',protectPendingSave);
    return Promise.resolve(promise)
      .then(result=>{vm.notify?.('客户资料已同步云端');return result})
      .catch(error=>{
        console.error(error);
        vm.notify?.('客户资料云端同步失败，请勿刷新页面，处理提示后重试');
        throw error;
      })
      .finally(()=>{
        pendingClientCloudSaves=Math.max(0,pendingClientCloudSaves-1);
        if(pendingClientCloudSaves===0)window.removeEventListener('beforeunload',protectPendingSave);
      });
  };
  const isClientDetailOpenButton=button=>{
    if(!button)return false;
    const label=text(button);
    if(label==='详情'||label==='查看客户详情')return true;
    const row=button.closest('tbody tr');
    return !!row&&button===row.querySelector('td:first-child button');
  };
  window.addEventListener('scroll',event=>{
    if(routeSwitching)return;
    const page=vm.currentPage||'';
    if(!PAGE_SCROLL_PAGES.has(page))return;
    const target=normalizeScrollTarget(event.target);
    if(!target)return;
    if(target!==documentScroller()&&!canOwnVerticalScroll(target))return;
    pageScrollTargets[page]=target;
    pageScrollPositions[page]=readTargetScrollTop(target);
  },{capture:true,passive:true});
  window.addEventListener('pointerdown',event=>{
    if(vm.currentPage!=='clients')return;
    const button=event.target?.closest?.('button');
    if(!isClientDetailOpenButton(button))return;
    lastClientPointerTarget=findScrollTarget(button);
    rememberPageScroll('clients',lastClientPointerTarget);
    pageScrollPositions['client-detail']=0;
    if(lastClientPointerTarget)pageScrollTargets['client-detail']=lastClientPointerTarget;
  },true);
  const originalOpenClientDetail=vm.openClientDetail;
  if(typeof originalOpenClientDetail==='function'){
    vm.openClientDetail=function(...args){
      const fromClients=vm.currentPage==='clients';
      if(fromClients){
        rememberPageScroll('clients',lastClientPointerTarget);
        pageScrollPositions['client-detail']=0;
        if(lastClientPointerTarget)pageScrollTargets['client-detail']=lastClientPointerTarget;
        routeSwitching=true;
      }
      try{
        const result=originalOpenClientDetail.apply(this,args);
        if(fromClients){
          const restore=()=>{
            if(vm.currentPage==='client-detail')restorePageScrollInstant('client-detail',lastClientPointerTarget);
            else routeSwitching=false;
          };
          if(typeof vm.$nextTick==='function')vm.$nextTick(restore);
          else queueMicrotask(restore);
        }
        return result;
      }catch(error){
        if(fromClients)routeSwitching=false;
        throw error;
      }
    };
  }
  function modalByButton(match){
    const button=[...document.querySelectorAll('button')].find(b=>match(text(b)));
    return button?.closest('.fixed.inset-0.modal-backdrop')||null;
  }
  const observePageScroll=()=>{
    const page=vm.currentPage||'';
    if(page===lastObservedPage)return;
    const previousPage=lastObservedPage;
    lastObservedPage=page;
    if(routeSwitching)return;
    if(!PAGE_SCROLL_PAGES.has(page))return;
    if(page==='client-form'&&previousPage!=='client-form')pageScrollPositions['client-form']=0;
    if(page==='client-detail'&&previousPage==='clients')pageScrollPositions['client-detail']=0;
    restorePageScrollInstant(page);
  };
  function install(){
    clearSessionRestoreCover();
    observePageScroll();
    bindModal(modalByButton(label=>label==='保存客户开户渠道'),'showOpeningModal',label=>label==='保存客户开户渠道','saveOpeningDeal');
    bindModal(modalByButton(label=>label==='保存开户商'),'showProviderModal',label=>label==='保存开户商','saveOpeningProvider');
    bindModal(modalByButton(label=>label.includes('保存并同步数据')||label.includes('更新并同步数据')),'showAdDataModal',label=>label.includes('保存并同步数据')||label.includes('更新并同步数据'),'saveAdDataRecord');
    if(vm.currentPage==='client-detail'){
      document.querySelectorAll('button').forEach(button=>{
        if(button.querySelector('i.fa-arrow-left'))bind(button,'client-detail-back',button=>navigateWithPageScroll('clients',button));
      });
    }
    if(vm.currentPage==='client-form'){
      document.querySelectorAll('button').forEach(button=>{
        const label=text(button),icon=button.querySelector('i.fa-arrow-left');
        if(label==='取消'||icon)bind(button,'client-form-back',button=>navigateWithPageScroll(vm.form?.id?'client-detail':'clients',button));
        if(label==='保存修改'||label==='确认合作并创建客户')bind(button,'client-form-save',()=>{
          if(button.dataset.growthopsClientSaving==='1')return;
          if(!validateButtonForm(button))return;
          if(typeof vm.saveClient!=='function'){vm.notify?.('客户保存功能未加载，请刷新页面');return}
          button.dataset.growthopsClientSaving='1';
          const cloud=window.__growthOpsCloud;
          const originalPersist=vm.persist;
          const originalNavigate=vm.navigateTo;
          let persistRequested=false;
          if(typeof cloud?.saveNow==='function'&&typeof originalPersist==='function')vm.persist=()=>{persistRequested=true;return true};
          if(typeof originalNavigate==='function')vm.navigateTo=()=>true;
          let result;
          try{result=vm.saveClient()}
          catch(error){
            delete button.dataset.growthopsClientSaving;
            console.error(error);
            vm.notify?.('客户保存失败，请稍后重试');
            return;
          }finally{
            if(vm.persist!==originalPersist)vm.persist=originalPersist;
            if(vm.navigateTo!==originalNavigate)vm.navigateTo=originalNavigate;
          }
          const complete=()=>{
            if(vm.formDirty!==false||!vm.selectedClientId){
              delete button.dataset.growthopsClientSaving;
              return;
            }
            finalizeClientListNavigation();
            delete button.dataset.growthopsClientSaving;
            if(persistRequested&&typeof cloud?.saveNow==='function'){
              requestAnimationFrame(()=>{
                vm.notify?.('客户已更新，正在同步云端…');
                trackClientCloudSave(cloud.saveNow()).catch(()=>{});
              });
            }
          };
          if(result&&typeof result.then==='function')result.then(()=>complete()).catch(error=>{
            delete button.dataset.growthopsClientSaving;
            console.error(error);
            vm.notify?.('客户保存失败，请稍后重试');
          });
          else complete();
        });
      });
    }
  }
  const observer=new MutationObserver(install);
  observer.observe(document.documentElement,{subtree:true,childList:true});
  setInterval(install,250);
  install();
  window.__GROWTHOPS_UI_ACTION_BRIDGE__={installed:true,version:'native-action-bridge-v18-real-scroll-targets'};
})();
