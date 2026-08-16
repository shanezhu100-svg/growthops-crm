(()=>{
  'use strict';
  const vm=window.__growthOpsVm;
  if(!vm)return;
  const BOUND='data-growthops-native-action';
  const TOKEN_KEY='growthops_crm_token_v2';
  const RETURN_CLIENT_KEY='growthops_ui_return_client_id';
  const RETURN_QUERY='_clientReturn';
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
  const setClientDetailUrl=()=>{
    try{
      const next=new URL(window.location.href);
      next.hash='client-detail';
      window.history.replaceState(window.history.state,'',next.toString());
    }catch{}
  };
  const finalizeClientNavigation=targetId=>{
    if(targetId!==null&&targetId!==undefined&&targetId!=='')vm.selectedClientId=targetId;
    vm.currentPage='client-detail';
    vm.mobileMenuOpen=false;
    setClientDetailUrl();
    try{vm.$forceUpdate?.()}catch{}
    requestAnimationFrame(()=>requestAnimationFrame(()=>{
      if(vm.currentPage!=='client-detail')vm.currentPage='client-detail';
      if(targetId!==null&&targetId!==undefined&&targetId!=='')vm.selectedClientId=targetId;
      try{vm.$forceUpdate?.()}catch{}
    }));
  };
  const hardClientReturn=targetId=>{
    try{
      sessionStorage.setItem(RETURN_CLIENT_KEY,String(targetId));
      const next=new URL(window.location.href);
      next.searchParams.set(RETURN_QUERY,String(Date.now()));
      next.hash='client-detail';
      window.location.replace(next.toString());
    }catch(error){
      console.error(error);
      vm.notify?.('客户已保存，但页面跳转失败，请刷新后查看客户详情');
    }
  };
  const restoreClientReturn=()=>{
    clearSessionRestoreCover();
    if(!vm.currentUser)return;
    let target='';
    try{target=sessionStorage.getItem(RETURN_CLIENT_KEY)||''}catch{}
    if(!target)return;
    const client=(vm.clients||[]).find(c=>String(c?.id)===String(target));
    if(!client)return;
    vm.selectedClientId=client.id;
    vm.currentPage='client-detail';
    setClientDetailUrl();
    try{vm.$forceUpdate?.()}catch{}
    try{
      sessionStorage.removeItem(RETURN_CLIENT_KEY);
      const next=new URL(window.location.href);
      if(next.searchParams.has(RETURN_QUERY)){
        next.searchParams.delete(RETURN_QUERY);
        next.hash='client-detail';
        window.history.replaceState(window.history.state,'',next.toString());
      }
    }catch{}
  };
  function modalByButton(match){
    const button=[...document.querySelectorAll('button')].find(b=>match(text(b)));
    return button?.closest('.fixed.inset-0.modal-backdrop')||null;
  }
  function install(){
    restoreClientReturn();
    bindModal(modalByButton(label=>label==='保存客户开户渠道'),'showOpeningModal',label=>label==='保存客户开户渠道','saveOpeningDeal');
    bindModal(modalByButton(label=>label==='保存开户商'),'showProviderModal',label=>label==='保存开户商','saveOpeningProvider');
    bindModal(modalByButton(label=>label.includes('保存并同步数据')||label.includes('更新并同步数据')),'showAdDataModal',label=>label.includes('保存并同步数据')||label.includes('更新并同步数据'),'saveAdDataRecord');
    if(vm.currentPage==='client-form'){
      document.querySelectorAll('button').forEach(button=>{
        const label=text(button),icon=button.querySelector('i.fa-arrow-left');
        if(label==='取消'||icon)bind(button,'client-form-back',()=>vm.navigateTo?.(vm.form?.id?'client-detail':'clients'));
        if(label==='保存修改'||label==='确认合作并创建客户')bind(button,'client-form-save',()=>{
          if(!validateButtonForm(button))return;
          if(typeof vm.saveClient!=='function'){vm.notify?.('客户保存功能未加载，请刷新页面');return}
          const cloud=window.__growthOpsCloud;
          const originalId=vm.form?.id||null;
          const originalPersist=vm.persist;
          let persistRequested=false;
          if(typeof cloud?.saveNow==='function'&&typeof originalPersist==='function'){
            vm.persist=()=>{persistRequested=true;return true};
          }
          let result;
          try{result=vm.saveClient()}
          finally{if(vm.persist!==originalPersist)vm.persist=originalPersist}
          const complete=async()=>{
            if(vm.formDirty!==false||!vm.selectedClientId)return;
            const targetId=originalId||vm.selectedClientId;
            if(persistRequested&&typeof cloud?.saveNow==='function'){
              try{await cloud.saveNow()}
              catch(error){console.error(error);vm.notify?.('客户资料未完成云端保存，请处理提示后重试');return}
            }
            try{sessionStorage.setItem(RETURN_CLIENT_KEY,String(targetId))}catch{}
            finalizeClientNavigation(targetId);
            setTimeout(()=>{
              const formStillVisible=button.isConnected&&button.getClientRects().length>0;
              if(formStillVisible||vm.currentPage!=='client-detail')hardClientReturn(targetId);
              else try{sessionStorage.removeItem(RETURN_CLIENT_KEY)}catch{}
            },450);
          };
          if(result&&typeof result.then==='function')result.then(()=>complete()).catch(error=>{console.error(error);vm.notify?.('客户保存失败，请稍后重试')});
          else complete().catch(error=>{console.error(error);vm.notify?.('客户保存后的页面切换失败，请重试')});
        });
      });
    }
  }
  const observer=new MutationObserver(install);
  observer.observe(document.documentElement,{subtree:true,childList:true});
  setInterval(install,250);
  install();
  window.__GROWTHOPS_UI_ACTION_BRIDGE__={installed:true,version:'native-action-bridge-v6'};
})();
