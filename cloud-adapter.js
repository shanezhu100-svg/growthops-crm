(()=>{
  const vm=window.__growthOpsVm;
  if(!vm)return;
  const SUPABASE_URL=window.__GROWTHOPS_SUPABASE_URL__||'';
  const API_KEY=window.__GROWTHOPS_SUPABASE_KEY__||'';
  const TOKEN_KEY='growthops_crm_token_v2';
  let token=localStorage.getItem(TOKEN_KEY)||'';
  let revision=0;
  let saveTimer=null;
  let saveChain=Promise.resolve();

  async function rpc(name,body={}){
    const r=await fetch(`${SUPABASE_URL}/rest/v1/rpc/${name}`,{method:'POST',headers:{apikey:API_KEY,'Content-Type':'application/json'},body:JSON.stringify(body)});
    let data=null;try{data=await r.json()}catch{}
    if(!r.ok)throw new Error(data?.message||data?.hint||`请求失败 ${r.status}`);
    return data;
  }
  function emptyState(){
    vm.clients=[];vm.standaloneAlerts=[];vm.reminderTypes=vm.defaultReminderTypes();vm.dismissedAlerts=[];vm.leads=[];vm.openingProviders=[];vm.openingDeals=[];vm.financeActualRebates=[];vm.financeReceivables=[];vm.financeCosts=[];vm.financeReconciliations=[];vm.financeMonthLocks={};vm.financeMonthSnapshots={};vm.backupSnapshots=[];vm.auditLogs=[];vm.mediaTools=[];vm.authUsers=[];
  }
  function applyState(p){
    p=p&&typeof p==='object'?p:{};
    if(Array.isArray(p.clients)) vm.clients=p.clients.map(c=>vm.normalizeClient(c));
    else if(Array.isArray(p.customers)) vm.clients=p.customers.map((c,i)=>vm.normalizeClient({id:c.id||Date.now()+i,name:c.name||`历史客户 ${i+1}`,product:c.note||'未填写产品',platform:c.platform==='TikTok'?'TK':c.platform==='Facebook'?'FB':'FB+TK',project:'历史客户迁移',currency:'USD',monthlyFee:0,billingMode:'MANUAL',startDate:String(c.createdAt||'').slice(0,10)||vm.localDateKey(),endDate:'2099-12-31',renewalAlertDay:25,status:c.status==='合作中'?'ACTIVE':'PAUSED',archived:false,fbAccounts:[],tkAccounts:[],networkEnvironments:[],googleAccounts:[],instagramAccounts:[],renewalHistory:[],adCampaigns:[],sopAccountConfigs:{}}));
    else vm.clients=[];
    vm.standaloneAlerts=(p.standaloneAlerts||[]).filter(a=>a?.typeKey!=='TOOL').map(a=>vm.normalizeStandaloneAlert(a));
    vm.reminderTypes=vm.normalizeReminderTypes(p.reminderTypes||vm.defaultReminderTypes());
    vm.dismissedAlerts=Array.isArray(p.dismissedAlerts)?p.dismissedAlerts:[];
    vm.leads=Array.isArray(p.leads)?p.leads:[];
    vm.openingProviders=(p.openingProviders||[]).map(x=>vm.normalizeOpeningProvider(x));
    vm.openingDeals=Array.isArray(p.openingDeals)?p.openingDeals:[];
    vm.migrateOpeningDeals();
    vm.financeActualRebates=vm.normalizeFinanceActualRebates(p.financeActualRebates||[]);
    vm.financeReceivables=(p.financeReceivables||[]).map(r=>vm.normalizeReceivable(r));
    vm.financeCosts=(p.financeCosts||[]).map(c=>vm.normalizeFinanceCost(c));
    vm.financeReconciliations=(p.financeReconciliations||[]).map(r=>({...r,status:r.status||'CONFIRMED'}));
    vm.financeMonthLocks=p.financeMonthLocks||{};
    vm.financeMonthSnapshots=p.financeMonthSnapshots||{};
    vm.backupSnapshots=Array.isArray(p.backupSnapshots)?p.backupSnapshots:[];
    vm.auditLogs=Array.isArray(p.auditLogs)?p.auditLogs:[];
    vm.mediaTools=(p.mediaTools||[]).map(t=>vm.normalizeMediaTool(t));
    if(p.sopProgress)vm.restoreSopProgress(p.sopProgress);
    vm.migrateLegacyActualRebatesToReconciliations();
    vm.ensureReceivableLinkedCosts();
    vm.ensureFinanceSnapshotsForLocks();
  }
  function payload(){
    const p=vm.collectBackupPayload();
    delete p.authUsers;
    p.version='growth-ops-cloud-v1';
    return JSON.parse(JSON.stringify(p));
  }
  async function loadUsers(){
    if(!token||vm.currentUser?.role!=='ADMIN'){vm.authUsers=vm.currentUser?[{...vm.currentUser,enabled:true,password:''}]:[];return;}
    try{const d=await rpc('crm_list_users',{p_token:token});const rows=Array.isArray(d)?d:(Array.isArray(d?.users)?d.users:[]);vm.authUsers=rows.map(u=>({...u,enabled:u.enabled!==false,password:''}));}
    catch{vm.authUsers=[{...vm.currentUser,enabled:true,password:''}];}
  }
  function syncSelections(){
    vm.selectedClientId=vm.activeClients[0]?.id||null;
    vm.selectedAssetsClientId=vm.activeClients[0]?.id||null;
    vm.selectedSopClientId=vm.activeClients[0]?.id||null;
    vm.selectedAnalyticsClientId=vm.activeClients[0]?.id||0;
    vm.selectedAdsClientId=vm.activeClients[0]?.id||0;
    vm.syncAnalyticsAccountSelection();vm.syncAdsAccountSelection();vm.syncSopAccountSelection(true);
  }
  async function enter(d){
    token=d?.token||token;revision=Number(d?.revision||0);if(token)localStorage.setItem(TOKEN_KEY,token);
    applyState(d?.state||{});vm.currentUser=d?.user||null;await loadUsers();syncSelections();
    if(vm.currentUser&&!vm.canViewPage(vm.currentPage))vm.currentPage='dashboard';
  }
  async function saveNow(){
    if(!token||!vm.currentUser)return true;
    const state=payload();
    try{const d=await rpc('crm_save_state',{p_token:token,p_state:state,p_expected_revision:revision});revision=Number(d?.revision??revision+1);return true;}
    catch(e){if(String(e.message).includes('CLOUD_REVISION_CONFLICT'))vm.notify('云端数据已被其他成员更新，请刷新页面后继续操作');throw e;}
  }
  vm.persist=()=>{clearTimeout(saveTimer);saveTimer=setTimeout(()=>{saveChain=saveChain.then(saveNow).catch(e=>{console.error(e);vm.notify(`云端保存失败：${e.message}`);});},180);return true;};
  vm.login=async()=>{try{const d=await rpc('crm_login',{p_username:String(vm.loginForm.username||'').trim(),p_password:String(vm.loginForm.password||'')});await enter(d);vm.logAudit('登录系统',`${vm.currentUser?.name||''} · ${vm.roleLabel(vm.currentUser?.role)}`);vm.persist();vm.notify('已连接 Supabase 云端数据');}catch(e){vm.notify(e?.message||'账号或密码错误');}};
  vm.logout=async()=>{const old=vm.currentUser;if(old)vm.logAudit('退出系统',old.name||'');try{if(token)await rpc('crm_logout',{p_token:token});}catch{}token='';revision=0;localStorage.removeItem(TOKEN_KEY);emptyState();vm.currentUser=null;vm.loginForm={username:'',password:''};vm.currentPage='dashboard';};
  async function boot(){
    emptyState();vm.currentUser=null;
    try{await rpc('crm_public_status');if(token){try{const d=await rpc('crm_load_state',{p_token:token});await enter(d);return;}catch{token='';localStorage.removeItem(TOKEN_KEY);}}}
    catch(e){vm.notify(`Supabase 连接失败：${e.message}`);}
  }
  window.__growthOpsCloud={rpc,saveNow,loadUsers};
  boot();
})();
