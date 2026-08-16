(()=>{
  'use strict';
  const vm=window.__growthOpsVm;
  if(!vm)return;
  const BOUND='data-growthops-native-action';
  const TOKEN_KEY='growthops_crm_token_v2';
  const PAGE_SCROLL_PAGES=new Set(['clients','client-form','client-detail']);
  const pageScrollPositions=Object.create(null);
  let pendingClientCloudSaves=0;
  let routeSwitching=false;
  let lastObservedPage=vm.currentPage||'';
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
  const readScrollTop=()=>{
    const scroller=document.scrollingElement||document.documentElement;
    return Math.max(0,Number(scroller?.scrollTop||document.documentElement?.scrollTop||document.body?.scrollTop||0));
  };
  const writeScrollTop=top=>{
    const value=Math.max(0,Number(top)||0);
    const scroller=document.scrollingElement||document.documentElement;
    if(scroller)scroller.scrollTop=value;
    if(document.documentElement&&document.documentElement!==scroller)document.documentElement.scrollTop=value;
    if(document.body&&document.body!==scroller)document.body.scrollTop=value;
  };
  const rememberPageScroll=(page=vm.currentPage)=>{
    if(routeSwitching||!PAGE_SCROLL_PAGES.has(page))return;
    pageScrollPositions[page]=readScrollTop();
  };
  const getPageScroll=page=>{
    const value=pageScrollPositions[page];
    return Number.isFinite(value)?Math.max(0,value):0;
  };
  const restorePageScrollInstant=page=>{
    const root=document.documentElement;
    const body=document.body;
    const oldRootBehavior=root.style.scrollBehavior;
    const oldBodyBehavior=body?.style?.scrollBehavior||'';
    root.style.scrollBehavior='auto';
    if(body)body.style.scrollBehavior='auto';
    writeScrollTop(getPageScroll(page));
    requestAnimationFrame(()=>{
      writeScrollTop(getPageScroll(page));
      root.style.scrollBehavior=oldRootBehavior;
      if(body)body.style.scrollBehavior=oldBodyBehavior;
    });
  };
  const navigateWithPageScroll=page=>{
    const sourcePage=vm.currentPage;
    if(sourcePage)rememberPageScroll(sourcePage);
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
    writeScrollTop(targetTop);
    try{vm.$forceUpdate?.()}catch{}
    const settle=()=>{
      if(vm.currentPage!==page){
        vm.currentPage=page;
        try{vm.$forceUpdate?.()}catch{}
      }
      writeScrollTop(targetTop);
      requestAnimationFrame(()=>{
        writeScrollTop(targetTop);
        routeSwitching=false;
        lastObservedPage=page;
        root.style.scrollBehavior=oldRootBehavior;
        if(body)body.style.scrollBehavior=oldBodyBehavior;
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
  function modalByButton(match){
    const button=[...document.querySelectorAll('button')].find(b=>match(text(b)));
    return button?.closest('.fixed.inset-0.modal-backdrop')||null;
  }
  const observePageScroll=()=>{
    const page=vm.currentPage||'';
    if(page===lastObservedPage){
      rememberPageScroll(page);
      return;
    }
    if(page==='client-form'&&lastObservedPage!=='client-form'&&!routeSwitching){
      pageScrollPositions['client-form']=0;
      restorePageScrollInstant('client-form');
    }
    lastObservedPage=page;
    rememberPageScroll(page);
  };
  window.addEventListener('scroll',()=>rememberPageScroll(vm.currentPage),{passive:true});
  function install(){
    clearSessionRestoreCover();
    observePageScroll();
    bindModal(modalByButton(label=>label==='保存客户开户渠道'),'showOpeningModal',label=>label==='保存客户开户渠道','saveOpeningDeal');
    bindModal(modalByButton(label=>label==='保存开户商'),'showProviderModal',label=>label==='保存开户商','saveOpeningProvider');
    bindModal(modalByButton(label=>label.includes('保存并同步数据')||label.includes('更新并同步数据')),'showAdDataModal',label=>label.includes('保存并同步数据')||label.includes('更新并同步数据'),'saveAdDataRecord');
    if(vm.currentPage==='client-form'){
      document.querySelectorAll('button').forEach(button=>{
        const label=text(button),icon=button.querySelector('i.fa-arrow-left');
        if(label==='取消'||icon)bind(button,'client-form-back',()=>navigateWithPageScroll(vm.form?.id?'client-detail':'clients'));
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
  window.__GROWTHOPS_UI_ACTION_BRIDGE__={installed:true,version:'native-action-bridge-v15-page-scroll-memory'};
})();
