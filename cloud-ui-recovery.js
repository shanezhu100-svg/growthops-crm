(()=>{
  'use strict';

  const vm=window.__growthOpsVm;
  if(!vm)return;

  const TOKEN_KEY='growthops_crm_token_v2';
  const SESSION_MASK_ID='growthops-session-restore-mask';
  const ERROR_BADGE_ID='growthops-ui-runtime-badge';

  function make(tag,attrs={},text=''){
    const el=document.createElement(tag);
    for(const [key,value] of Object.entries(attrs)){
      if(key==='style')el.style.cssText=value;
      else el.setAttribute(key,String(value));
    }
    if(text)el.textContent=text;
    return el;
  }

  function installSessionRestoreMask(){
    let token='';
    try{token=localStorage.getItem(TOKEN_KEY)||''}catch{}
    if(!token)return;
    if(document.getElementById(SESSION_MASK_ID))return;

    const overlay=make('div',{
      id:SESSION_MASK_ID,
      style:'position:fixed;inset:0;z-index:2147483400;background:#0f172a;display:flex;align-items:center;justify-content:center;padding:24px;color:#fff;font:14px/1.5 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;'
    });
    const card=make('div',{style:'width:min(420px,92vw);padding:24px;border-radius:20px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.12);text-align:center;box-shadow:0 24px 80px rgba(0,0,0,.25);'});
    card.appendChild(make('div',{style:'font-size:16px;font-weight:800;'},'正在恢复安全会话'));
    card.appendChild(make('div',{style:'margin-top:8px;font-size:12px;color:#cbd5e1;'},'正在加载云端工作区，请稍候…'));
    overlay.appendChild(card);
    document.body.appendChild(overlay);

    const started=Date.now();
    const timer=setInterval(()=>{
      let currentToken='';
      try{currentToken=localStorage.getItem(TOKEN_KEY)||''}catch{}
      if(vm.currentUser||!currentToken||Date.now()-started>12000){
        clearInterval(timer);
        overlay.remove();
      }
    },50);
  }

  function reportRuntime(code){
    const safe={code:String(code||'UI-RUNTIME-01'),page:String(vm.currentPage||'unknown'),at:new Date().toISOString()};
    try{sessionStorage.setItem('growthops_ui_runtime_error_v1',JSON.stringify(safe))}catch{}
    let badge=document.getElementById(ERROR_BADGE_ID);
    if(!badge){
      badge=make('div',{
        id:ERROR_BADGE_ID,
        style:'position:fixed;left:16px;bottom:16px;z-index:2147483500;max-width:min(520px,calc(100vw - 32px));padding:10px 12px;border-radius:12px;background:#7f1d1d;color:#fff;font:700 12px/1.4 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;box-shadow:0 12px 32px rgba(0,0,0,.25);pointer-events:none;'
      });
      document.body.appendChild(badge);
    }
    badge.textContent=`页面运行异常 ${safe.code} · ${safe.page}。请保留当前页面并反馈该错误码。`;
  }

  const appConfig=vm?.$?.appContext?.config;
  if(appConfig){
    const previous=appConfig.errorHandler;
    appConfig.errorHandler=(error,instance,info)=>{
      reportRuntime('UI-VUE-01');
      if(typeof previous==='function'){
        try{previous(error,instance,info)}catch{}
      }
    };
  }

  window.addEventListener('error',()=>reportRuntime('UI-JS-01'));
  window.addEventListener('unhandledrejection',()=>reportRuntime('UI-ASYNC-01'));

  let forceQueued=false;
  function queueRenderRecovery(){
    if(forceQueued)return;
    forceQueued=true;
    queueMicrotask(()=>{
      forceQueued=false;
      try{if(typeof vm.$forceUpdate==='function')vm.$forceUpdate()}catch{reportRuntime('UI-FORCE-01')}
    });
  }
  document.addEventListener('click',queueRenderRecovery,false);
  document.addEventListener('submit',queueRenderRecovery,false);

  installSessionRestoreMask();

  window.__GROWTHOPS_UI_RECOVERY__={
    installed:true,
    version:'ui-recovery-v1',
    features:['session-restore-mask','post-interaction-force-render','sanitized-runtime-error-code']
  };
})();
