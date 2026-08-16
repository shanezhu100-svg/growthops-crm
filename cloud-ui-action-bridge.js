(()=>{
  'use strict';
  const vm=window.__growthOpsVm;
  if(!vm)return;
  const BOUND='data-growthops-native-action';
  const TOKEN_KEY='growthops_crm_token_v2';
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
  const settleScrollTop=()=>{
    const apply=()=>{
      const scroller=document.scrollingElement||document.documentElement;
      if(scroller)scroller.scrollTop=0;
      if(document.body)document.body.scrollTop=0;
    };
    if(typeof vm.$nextTick==='function')vm.$nextTick(apply);
    else queueMicrotask(apply);
  };
  const quietNavigate=page=>{
    vm.currentPage=page;
    vm.mobileMenuOpen=false;
    setPageUrl(page);
    settleScrollTop();
  };
  const finalizeClientListNavigation=()=>quietNavigate('clients');
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
        if(label==='取消'||icon)bind(button,'client-form-back',()=>quietNavigate(vm.form?.id?'client-detail':'clients'));
        if(label==='保存修改'||label==='确认合作并创建客户')bind(button,'client-form-save',()=>{
          if(!validateButtonForm(button))return;
          if(typeof vm.saveClient!=='function'){vm.notify?.('客户保存功能未加载，请刷新页面');return}
          const cloud=window.__growthOpsCloud;
          const originalPersist=vm.persist;
          let persistRequested=false;
          if(typeof cloud?.saveNow==='function'&&typeof originalPersist==='function')vm.persist=()=>{persistRequested=true;return true};
          let result;
          try{result=vm.saveClient()}
          finally{if(vm.persist!==originalPersist)vm.persist=originalPersist}
          const complete=()=>{
            if(vm.formDirty!==false||!vm.selectedClientId)return;
            finalizeClientListNavigation();
            if(persistRequested&&typeof cloud?.saveNow==='function'){
              vm.notify?.('客户已更新，正在同步云端…');
              trackClientCloudSave(cloud.saveNow()).catch(()=>{});
            }
          };
          if(result&&typeof result.then==='function')result.then(()=>complete()).catch(error=>{console.error(error);vm.notify?.('客户保存失败，请稍后重试')});
          else complete();
        });
      });
    }
  }
  const observer=new MutationObserver(install);
  observer.observe(document.documentElement,{subtree:true,childList:true});
  setInterval(install,250);
  install();
  window.__GROWTHOPS_UI_ACTION_BRIDGE__={installed:true,version:'native-action-bridge-v11-fast-save'};
})();
