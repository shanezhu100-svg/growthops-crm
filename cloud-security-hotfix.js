(()=>{
  'use strict';

  const vm=window.__growthOpsVm;
  const cloud=window.__growthOpsCloud;
  if(!vm||!cloud||typeof cloud.rpc!=='function')return;

  const TOKEN_KEY='growthops_crm_token_v2';
  const BUTTON_ID='growthops-secure-credential-button';
  const MODAL_ID='growthops-secure-credential-modal';
  const SECRET_KEYS=new Set([
    'password','loginpassword','login_password','passwd','pwd',
    'loginaccount','login_account',
    'fbloginaccount','fbloginpassword','tkloginaccount','tkloginpassword',
    'twofactor','two_factor','twofactorsecret','two_factor_secret','twofakey','two_fa_key',
    '2fa','2fakey','2fa_key','backupcodes','backup_codes','recoverycodes','recovery_codes',
    'totpsecret','totp_secret','secretkey','secret_key'
  ]);

  let revealData=null;
  let revealTimer=null;

  const clone=value=>JSON.parse(JSON.stringify(value));
  const isSecretKey=key=>SECRET_KEYS.has(String(key||'').toLowerCase());

  function redactSecrets(value){
    if(Array.isArray(value))return value.map(redactSecrets);
    if(value&&typeof value==='object'){
      const out={};
      for(const [key,val] of Object.entries(value)){
        if(isSecretKey(key))continue;
        out[key]=redactSecrets(val);
      }
      return out;
    }
    return value;
  }

  function buildRedactedSnapshotPayload(){
    const raw=typeof vm.collectBackupPayload==='function'?vm.collectBackupPayload():{};
    const payload=raw&&typeof raw==='object'&&!Array.isArray(raw)?clone(raw):{};
    delete payload.authUsers;
    delete payload.backupSnapshots;
    payload.version='growth-ops-cloud-backup-v3-redacted';
    const redacted=redactSecrets(payload);
    redacted.redacted=true;
    redacted.redaction={
      version:'crm-secret-keys-v2',
      appliedAt:new Date().toISOString(),
      behavior:'secret keys removed recursively before cloud snapshot persistence'
    };
    return redacted;
  }

  vm.createBackupSnapshot=(notifyUser=false)=>{
    const snap={
      id:vm.accountUid('backup'),
      name:`数据快照 ${vm.localDateKey()} ${new Date().toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit'})}`,
      backupDate:vm.localDateKey(),
      createdAt:new Date().toISOString(),
      payload:buildRedactedSnapshotPayload()
    };
    vm.backupSnapshots.unshift(snap);
    vm.backupSnapshots=vm.backupSnapshots.slice(0,5);
    vm.persist();
    vm.updateStorageUsage();
    if(notifyUser){
      vm.logAudit('创建脱敏数据快照',snap.name);
      vm.persist();
      vm.notify('已创建脱敏云端数据快照；客户密码、2FA 与恢复码未写入快照');
    }
    return snap;
  };

  function flattenSecretFields(value,path=[],out=[]){
    if(Array.isArray(value)){
      value.forEach((item,index)=>{
        const id=item&&typeof item==='object'&&item.id!=null?String(item.id):String(index+1);
        flattenSecretFields(item,[...path,`#${id}`],out);
      });
      return out;
    }
    if(!value||typeof value!=='object')return out;

    for(const [key,val] of Object.entries(value)){
      if(key==='id')continue;
      if(isSecretKey(key)){
        let display='';
        if(Array.isArray(val))display=val.map(v=>String(v??'')).filter(Boolean).join('\n');
        else if(val&&typeof val==='object')display=JSON.stringify(val);
        else display=String(val??'');
        if(display)out.push({label:[...path,key].join(' / '),value:display});
      }else{
        flattenSecretFields(val,[...path,key],out);
      }
    }
    return out;
  }

  function clearReveal(){
    clearTimeout(revealTimer);
    revealTimer=null;
    revealData=null;
    const modal=document.getElementById(MODAL_ID);
    if(modal)modal.remove();
  }

  function make(tag,attrs={},text=''){
    const el=document.createElement(tag);
    for(const [key,val] of Object.entries(attrs)){
      if(key==='style')el.style.cssText=val;
      else if(key==='className')el.className=val;
      else el.setAttribute(key,String(val));
    }
    if(text)el.textContent=text;
    return el;
  }

  function renderRevealModal(clientId,secretTree){
    clearReveal();
    revealData=secretTree;
    const fields=flattenSecretFields(secretTree);

    const overlay=make('div',{id:MODAL_ID,style:'position:fixed;inset:0;z-index:2147483600;background:rgba(15,23,42,.58);display:flex;align-items:center;justify-content:center;padding:24px;'});
    const card=make('div',{style:'width:min(760px,96vw);max-height:88vh;overflow:auto;background:#fff;border-radius:18px;box-shadow:0 24px 70px rgba(15,23,42,.28);padding:22px;font:14px/1.45 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#0f172a;'});
    const head=make('div',{style:'display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:16px;'});
    const titleWrap=make('div');
    titleWrap.appendChild(make('div',{style:'font-size:18px;font-weight:750;'},'客户敏感凭证 · 临时查看'));
    titleWrap.appendChild(make('div',{style:'margin-top:5px;color:#64748b;font-size:12px;'},`客户 ID ${clientId} · 60 秒后自动清除；不会写入快照或审计详情`));
    const close=make('button',{type:'button',style:'border:0;background:#f1f5f9;border-radius:10px;padding:8px 11px;cursor:pointer;font-weight:700;'},'关闭');
    close.addEventListener('click',clearReveal);
    head.appendChild(titleWrap);
    head.appendChild(close);
    card.appendChild(head);

    if(!fields.length){
      card.appendChild(make('div',{style:'padding:18px;border:1px dashed #cbd5e1;border-radius:12px;color:#64748b;'},'该客户当前没有可显示的密码、2FA Secret 或 Recovery Codes。'));
    }else{
      const warning=make('div',{style:'margin-bottom:14px;padding:10px 12px;border-radius:12px;background:#fff7ed;color:#9a3412;font-size:12px;'},'敏感值默认保持隐藏。只有当前 ADMIN 点击“显示”后才会在本浏览器短暂显示。请勿截图、转发或粘贴到聊天/工单。');
      card.appendChild(warning);

      fields.forEach(field=>{
        const row=make('div',{style:'padding:12px 0;border-top:1px solid #e2e8f0;'});
        row.appendChild(make('div',{style:'font-size:12px;color:#475569;margin-bottom:7px;word-break:break-all;'},field.label));
        const controls=make('div',{style:'display:flex;gap:8px;align-items:center;'});
        const valueBox=make('div',{style:'flex:1;min-height:38px;padding:9px 11px;border:1px solid #cbd5e1;border-radius:10px;background:#f8fafc;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;white-space:pre-wrap;word-break:break-all;'},'••••••••');
        let visible=false;
        const toggle=make('button',{type:'button',style:'border:1px solid #cbd5e1;background:#fff;border-radius:9px;padding:8px 10px;cursor:pointer;font-weight:650;'},'显示');
        toggle.addEventListener('click',()=>{
          visible=!visible;
          valueBox.textContent=visible?field.value:'••••••••';
          toggle.textContent=visible?'隐藏':'显示';
        });
        controls.appendChild(valueBox);
        controls.appendChild(toggle);
        row.appendChild(controls);
        card.appendChild(row);
      });
    }

    overlay.appendChild(card);
    overlay.addEventListener('click',event=>{if(event.target===overlay)clearReveal();});
    document.body.appendChild(overlay);
    revealTimer=setTimeout(clearReveal,60000);
  }

  async function revealSelectedClient(){
    if(vm.currentUser?.role!=='ADMIN'){
      vm.notify('只有管理员可以查看客户敏感凭证');
      return;
    }
    const clientId=vm.selectedClientId;
    if(clientId==null||clientId===''){
      vm.notify('请先选择客户');
      return;
    }
    const token=localStorage.getItem(TOKEN_KEY)||'';
    if(!token){
      vm.notify('当前会话已失效，请重新登录');
      return;
    }

    const button=document.getElementById(BUTTON_ID);
    if(button)button.disabled=true;
    try{
      const data=await cloud.rpc('crm_reveal_client_secrets',{p_token:token,p_client_id:String(clientId)});
      renderRevealModal(String(clientId),data&&typeof data==='object'?data:{});
    }catch(error){
      vm.notify(error?.message||'读取客户凭证失败');
    }finally{
      if(button)button.disabled=false;
    }
  }

  function ensureRevealButton(){
    let button=document.getElementById(BUTTON_ID);
    if(!button){
      button=make('button',{
        id:BUTTON_ID,
        type:'button',
        style:'position:fixed;right:18px;bottom:72px;z-index:2147482500;border:0;border-radius:999px;background:#0f172a;color:#fff;padding:10px 14px;box-shadow:0 10px 30px rgba(15,23,42,.2);font:700 13px/1.2 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;cursor:pointer;'
      },'安全查看客户凭证');
      button.addEventListener('click',revealSelectedClient);
      document.body.appendChild(button);
    }

    const visible=vm.currentUser?.role==='ADMIN'&&vm.currentPage==='client-detail'&&vm.selectedClientId!=null;
    button.style.display=visible?'block':'none';
  }

  document.addEventListener('visibilitychange',()=>{
    if(document.hidden)clearReveal();
  });
  window.addEventListener('beforeunload',clearReveal);

  setInterval(ensureRevealButton,300);
  ensureRevealButton();

  window.__GROWTHOPS_SECURITY_HOTFIX__={
    installed:true,
    version:'vault-redacted-v1',
    features:[
      'redacted-cloud-snapshots',
      'admin-on-demand-client-secret-reveal',
      '60-second-reveal-auto-clear'
    ],
    secretKeyCount:SECRET_KEYS.size
  };
})();
