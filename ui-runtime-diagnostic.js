(()=>{
  'use strict';
  const vm=window.__growthOpsVm;
  if(!vm||window.__GROWTHOPS_UI_RUNTIME_DIAG__)return;

  const BOUND='data-growthops-native-action';
  const MAX_LINES=7;
  const lines=[];
  const state=()=>({
    page:String(vm.currentPage||''),
    selectedIdType:vm.selectedClientId==null?'none':typeof vm.selectedClientId,
    selectedClient:!!vm.selectedClient,
    formId:!!vm.form?.id,
    dirty:!!vm.formDirty
  });
  const esc=value=>String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const safeError=error=>{
    const name=String(error?.name||'Error').replace(/[^A-Za-z0-9_$.-]/g,'').slice(0,40)||'Error';
    const raw=String(error?.message||'').replace(/https?:\/\/\S+/g,'[url]').replace(/[\r\n]+/g,' ').slice(0,140);
    return `${name}${raw?`: ${raw}`:''}`;
  };
  const snapshotText=s=>`page=${s.page||'—'} selected=${s.selectedClient?'yes':'no'} idType=${s.selectedIdType} form=${s.formId?'edit':'new/none'} dirty=${s.dirty?'yes':'no'}`;

  let panel=null;
  function ensurePanel(){
    if(panel?.isConnected)return panel;
    panel=document.createElement('div');
    panel.id='growthops-ui-runtime-diag';
    panel.style.cssText='position:fixed;left:12px;bottom:12px;z-index:2147483646;width:min(680px,calc(100vw - 24px));max-height:42vh;overflow:auto;pointer-events:none;background:rgba(15,23,42,.94);color:#e2e8f0;border:1px solid rgba(148,163,184,.45);border-radius:12px;padding:10px 12px;box-shadow:0 12px 40px rgba(15,23,42,.28);font:11px/1.45 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;white-space:normal;';
    document.body.appendChild(panel);
    render();
    return panel;
  }
  function render(){
    if(!panel?.isConnected)return;
    panel.innerHTML=`<div style="font-weight:800;color:#fff;margin-bottom:5px">UI DIAG · 只读诊断</div>${lines.length?lines.map(line=>`<div style="border-top:1px solid rgba(148,163,184,.18);padding:3px 0">${esc(line)}</div>`).join(''):'<div>等待点击：详情 / 返回 / 取消</div>'}`;
  }
  function log(message){
    lines.unshift(`${new Date().toLocaleTimeString('zh-CN',{hour12:false})} ${message}`);
    lines.splice(MAX_LINES);
    ensurePanel();render();
  }
  function sample(label){
    const capture=()=>log(`${label} · ${snapshotText(state())}`);
    queueMicrotask(capture);
    setTimeout(capture,60);
    setTimeout(capture,260);
  }

  function knownAction(button){
    if(!button)return'';
    const label=String(button.textContent||'').replace(/\s+/g,' ').trim();
    if(vm.currentPage==='clients'){
      if(label==='详情'||label==='查看客户详情')return'DETAIL';
      const row=button.closest('tbody tr');
      if(row&&button===row.querySelector('td:first-child button'))return'DETAIL_NAME';
    }
    if(vm.currentPage==='client-form'){
      if(label==='取消')return'CANCEL';
      if(button.querySelector('i.fa-arrow-left'))return'BACK';
      if(label==='保存修改'||label==='确认合作并创建客户')return'SAVE';
    }
    return'';
  }
  function hitSummary(event){
    let stack=[];
    try{stack=document.elementsFromPoint(event.clientX,event.clientY).slice(0,4)}catch{}
    const top=stack[0]||event.target;
    const tag=String(top?.tagName||'').toLowerCase()||'none';
    const id=String(top?.id||'').startsWith('growthops-')?`#${top.id}`:'';
    const cls=String(top?.className||'').split(/\s+/).filter(Boolean).slice(0,3).join('.');
    const button=(event.target?.closest?.('button'))||stack.map(node=>node?.closest?.('button')).find(Boolean)||null;
    return {button,top:`${tag}${id}${cls?'.'+cls:''}`.slice(0,130)};
  }

  window.addEventListener('pointerdown',event=>{
    const hit=hitSummary(event);const action=knownAction(hit.button);
    if(!action)return;
    const binding=hit.button?.getAttribute?.(BOUND)||'none';
    log(`pointer ${action} top=${hit.top} bridge=${binding} · ${snapshotText(state())}`);
  },true);
  window.addEventListener('click',event=>{
    const hit=hitSummary(event);const action=knownAction(hit.button);
    if(action)log(`click ${action} top=${hit.top} · ${snapshotText(state())}`);
  },true);

  const originalOpenClientDetail=vm.openClientDetail;
  if(typeof originalOpenClientDetail==='function'){
    vm.openClientDetail=function(...args){
      log(`CALL openClientDetail(idType=${args[0]==null?'none':typeof args[0]}) BEFORE · ${snapshotText(state())}`);
      try{
        const result=originalOpenClientDetail.apply(this,args);
        log(`RETURN openClientDetail · ${snapshotText(state())}`);
        sample('AFTER openClientDetail');
        return result;
      }catch(error){
        log(`ERROR openClientDetail ${safeError(error)}`);
        throw error;
      }
    };
  }

  const originalNavigateTo=vm.navigateTo;
  if(typeof originalNavigateTo==='function'){
    vm.navigateTo=function(page,...rest){
      const target=String(page||'');
      if(['client-detail','clients','client-form'].includes(target))log(`CALL navigateTo(${target}) BEFORE · ${snapshotText(state())} canView=${typeof vm.canViewPage==='function'?String(!!vm.canViewPage(target)):'unknown'}`);
      try{
        const result=originalNavigateTo.call(this,page,...rest);
        if(['client-detail','clients','client-form'].includes(target)){
          log(`RETURN navigateTo(${target}) · ${snapshotText(state())}`);
          sample(`AFTER navigateTo(${target})`);
        }
        return result;
      }catch(error){
        if(['client-detail','clients','client-form'].includes(target))log(`ERROR navigateTo(${target}) ${safeError(error)}`);
        throw error;
      }
    };
  }

  window.addEventListener('error',event=>log(`WINDOW ERROR ${safeError(event.error||new Error(event.message||'unknown'))}`));
  window.addEventListener('unhandledrejection',event=>log(`PROMISE ERROR ${safeError(event.reason)}`));
  try{
    const appConfig=vm.$?.appContext?.config;
    if(appConfig){
      const previous=appConfig.errorHandler;
      appConfig.errorHandler=(error,instance,info)=>{
        log(`VUE ERROR stage=${String(info||'').slice(0,70)} ${safeError(error)}`);
        if(typeof previous==='function')return previous(error,instance,info);
      };
    }
  }catch{}

  ensurePanel();
  log(`DIAG READY · ${snapshotText(state())}`);
  window.__GROWTHOPS_UI_RUNTIME_DIAG__={installed:true,version:'client-nav-diag-v1',getLines:()=>[...lines]};
})();
