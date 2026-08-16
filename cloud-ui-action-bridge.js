(()=>{
  'use strict';
  const vm=window.__growthOpsVm;
  if(!vm)return;
  const BOUND='data-growthops-native-action';
  const TOKEN_KEY='growthops_crm_token_v2';
  const SAVE_TRANSITION_MS=180;
  const SAVE_TRANSITION_ID='growthops-client-save-transition';
  let pendingClientCloudSaves=0;
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
  const resetScrollNow=()=>{
    const scroller=document.scrollingElement||document.documentElement;
    if(scroller)scroller.scrollTop=0;
    if(document.documentElement)document.documentElement.scrollTop=0;
    if(document.body)document.body.scrollTop=0;
  };
  const navigateNoCarry=page=>{
    const root=document.documentElement;
    const body=document.body;
    const oldRootBehavior=root.style.scrollBehavior;
    const oldBodyBehavior=body?.style?.scrollBehavior||'';
    root.style.scrollBehavior='auto';
    if(body)body.style.scrollBehavior='auto';
    resetScrollNow();
    vm.currentPage=page;
    vm.mobileMenuOpen=false;
    setPageUrl(page);
    try{vm.$forceUpdate?.()}catch{}
    const settle=()=>{
      if(vm.currentPage!==page){
        vm.currentPage=page;
        try{vm.$forceUpdate?.()}catch{}
      }
      resetScrollNow();
      requestAnimationFrame(()=>{
        resetScrollNow();
        root.style.scrollBehavior=oldRootBehavior;
        if(body)body.style.scrollBehavior=oldBodyBehavior;
      });
    };
    if(typeof vm.$nextTick==='function')vm.$nextTick(settle);
    else queueMicrotask(settle);
  };
  const finalizeClientListNavigation=()=>navigateNoCarry('clients');
  const showClientSaveTransition=()=>{
    const old=document.getElementById(SAVE_TRANSITION_ID);
    if(old)old.remove();
    const cover=document.createElement('div');
    cover.id=SAVE_TRANSITION_ID;
    cover.setAttribute('role','status');
    cover.setAttribute('aria-live','polite');
    cover.style.cssText='position:fixed;inset:0;z-index:460;display:flex;align-items:center;justify-content:center;background:rgba(248,250,252,.97);opacity:1;transition:opacity 90ms ease;pointer-events:auto;';
    const panel=document.createElement('div');
    panel.textContent='正在保存客户…';
    panel.style.cssText='padding:13px 20px;border-radius:12px;background:#fff;border:1px solid #e2e8f0;box-shadow:0 12px 32px rgba(15,23,42,.10);font-weight:700;color:#0f172a;';
    cover.appendChild(panel);
    document.body.appendChild(cover);
    return cover;
  };
  const hideClientSaveTransition=()=>{
    const cover=document.getElementById(SAVE_TRANSITION_ID);
    if(!cover)return;
    cover.style.opacity='0';
    setTimeout(()=>cover.remove(),90);
  };
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
  function install(){
    clearSessionRestoreCover();
    bindModal(modalByButton(label=>label==='保存客户开户渠道'),'showOpeningModal',label=>label==='保存客户开户渠道','saveOpeningDeal');
    bindModal(modalByButton(label=>label==='保存开户商'),'showProviderModal',label=>label==='保存开户商','saveOpeningProvider');
    bindModal(modalByButton(label=>label.includes('保存并同步数据')||label.includes('更新并同步数据')),'showAdDataModal',label=>label.includes('保存并同步数据')||label.includes('更新并同步数据'),'saveAdDataRecord');
    if(vm.currentPage==='client-form'){
      document.querySelectorAll('button').forEach(button=>{
        const label=text(button),icon=button.querySelector('i.fa-arrow-left');
        if(label==='取消'||icon)bind(button,'client-form-back',()=>navigateNoCarry(vm.form?.id?'client-detail':'clients'));
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
            showClientSaveTransition();
            finalizeClientListNavigation();
            if(persistRequested&&typeof cloud?.saveNow==='function'){
              requestAnimationFrame(()=>{
                vm.notify?.('客户已更新，正在同步云端…');
                trackClientCloudSave(cloud.saveNow()).catch(()=>{});
              });
            }
            setTimeout(()=>{
              hideClientSaveTransition();
              delete button.dataset.growthopsClientSaving;
            },SAVE_TRANSITION_MS);
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
  window.__GROWTHOPS_UI_ACTION_BRIDGE__={installed:true,version:'native-action-bridge-v14-save-transition'};
})();
