(()=>{
  'use strict';
  const vm=window.__growthOpsVm;
  if(!vm)return;
  const BOUND='data-growthops-native-action';
  const TOKEN_KEY='growthops_crm_token_v2';
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
  const instantNavigate=page=>{
    const root=document.documentElement;
    const body=document.body;
    const oldRoot=root.style.scrollBehavior;
    const oldBody=body?.style?.scrollBehavior||'';
    root.style.scrollBehavior='auto';
    if(body)body.style.scrollBehavior='auto';
    vm.currentPage=page;
    vm.mobileMenuOpen=false;
    setPageUrl(page);
    try{vm.$forceUpdate?.()}catch{}
    try{window.scrollTo({top:0,left:0,behavior:'auto'})}catch{window.scrollTo(0,0)}
    requestAnimationFrame(()=>{
      if(vm.currentPage!==page)vm.currentPage=page;
      try{vm.$forceUpdate?.()}catch{}
      try{window.scrollTo({top:0,left:0,behavior:'auto'})}catch{window.scrollTo(0,0)}
      root.style.scrollBehavior=oldRoot;
      if(body)body.style.scrollBehavior=oldBody;
    });
  };
  const finalizeClientListNavigation=()=>instantNavigate('clients');
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
        if(label==='取消'||icon)bind(button,'client-form-back',()=>instantNavigate(vm.form?.id?'client-detail':'clients'));
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
          const complete=async()=>{
            if(vm.formDirty!==false||!vm.selectedClientId)return;
            if(persistRequested&&typeof cloud?.saveNow==='function'){
              try{await cloud.saveNow()}
              catch(error){console.error(error);vm.notify?.('客户资料未完成云端保存，请处理提示后重试');return}
            }
            finalizeClientListNavigation();
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
  window.__GROWTHOPS_UI_ACTION_BRIDGE__={installed:true,version:'native-action-bridge-v8'};
})();
