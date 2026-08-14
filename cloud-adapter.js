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
    vm.migrateLegacyAccountSpendRecords();
    vm.migrateLegacyActualRebatesToReconciliations();
    vm.ensureAutomaticReceivables({silent:true});
    vm.ensureAutomaticAssetCosts({month:vm.localDateKey().slice(0,7),silent:true});
    vm.ensureAutomaticOpeningFeeCosts();
    vm.ensureReceivableLinkedCosts();
    vm.ensureFinanceSnapshotsForLocks();
  }
  function payload(){
    const p=vm.collectBackupPayload();
    delete p.authUsers;
    p.backupSnapshots=Array.isArray(vm.backupSnapshots)?vm.backupSnapshots:[];
    p.version='growth-ops-cloud-v2';
    return JSON.parse(JSON.stringify(p));
  }
  function sanitizedBackupPayload(){
    const p=vm.collectBackupPayload();
    delete p.authUsers;
    delete p.backupSnapshots;
    p.version='growth-ops-cloud-backup-v2';
    return JSON.parse(JSON.stringify(p));
  }
  async function loadUsers(){
    if(!token||vm.currentUser?.role!=='ADMIN'){vm.authUsers=vm.currentUser?[{...vm.currentUser,enabled:true,password:''}]:[];return;}
    try{const d=await rpc('crm_list_users',{p_token:token});const rows=Array.isArray(d)?d:(Array.isArray(d?.users)?d.users:[]);vm.authUsers=rows.map(u=>({...u,enabled:u.enabled!==false,password:''}));}
    catch{vm.authUsers=vm.currentUser?[{...vm.currentUser,enabled:true,password:''}]:[];}
  }
  function syncSelections(){
    vm.selectedClientId=vm.activeClients[0]?.id||null;
    vm.selectedAssetsClientId=vm.activeClients[0]?.id||null;
    vm.selectedSopClientId=vm.activeClients[0]?.id||null;
    vm.selectedAnalyticsClientId=vm.activeClients[0]?.id||0;
    vm.selectedAdsClientId=vm.activeClients[0]?.id||0;
    vm.syncAnalyticsAccountSelection();vm.syncAdsAccountSelection();vm.syncSopAccountSelection(true);
  }
  function routeFromHash(){
    const h=window.location.hash.slice(1);
    const allowed=['dashboard','leads','clients','account-opening','alerts','assets','sop','ads','analytics','finance','tools','system','client-detail','client-form'];
    if(allowed.includes(h)&&vm.canViewPage(h))vm.currentPage=h;
    else if(vm.currentUser&&!vm.canViewPage(vm.currentPage))vm.currentPage='dashboard';
  }
  async function enter(d){
    token=d?.token||token;revision=Number(d?.revision||0);if(token)localStorage.setItem(TOKEN_KEY,token);
    applyState(d?.state||{});vm.currentUser=d?.user||null;await loadUsers();syncSelections();routeFromHash();
    const before=vm.backupSnapshots.length;
    vm.ensureDailyBackup();
    if(vm.backupSnapshots.length!==before)vm.persist();
    vm.updateStorageUsage();
  }
  async function saveNow(){
    if(!token||!vm.currentUser)return true;
    const state=payload();
    try{const d=await rpc('crm_save_state',{p_token:token,p_state:state,p_expected_revision:revision});revision=Number(d?.revision??revision+1);return true;}
    catch(e){if(String(e.message).includes('CLOUD_REVISION_CONFLICT'))vm.notify('云端数据已被其他成员更新，请刷新页面后继续操作');throw e;}
  }
  vm.persist=()=>{clearTimeout(saveTimer);saveTimer=setTimeout(()=>{saveChain=saveChain.then(saveNow).catch(e=>{console.error(e);vm.notify(`云端保存失败：${e.message}`);});},180);return true;};

  vm.openUserModal=(user=null)=>{
    if(vm.currentUser?.role!=='ADMIN'){vm.notify('只有管理员可以管理用户');return;}
    vm.userForm=user?{id:user.id,name:user.name||'',username:user.username||'',password:'',role:user.role||'OPS',enabled:user.enabled!==false}:{id:null,name:'',username:'',password:'',role:'OPS',enabled:true};
    vm.showUserModal=true;
  };
  vm.saveAuthUser=async()=>{
    if(vm.currentUser?.role!=='ADMIN'){vm.notify('只有管理员可以管理用户');return;}
    const f={...vm.userForm,name:String(vm.userForm.name||'').trim(),username:String(vm.userForm.username||'').trim(),password:String(vm.userForm.password||'')};
    if(!f.name||!f.username){vm.notify('请完整填写姓名和登录账号');return;}
    if(!f.id&&f.password.length<10){vm.notify('新用户登录密码至少需要 10 位');return;}
    if(f.id&&f.password&&f.password.length<10){vm.notify('新密码至少需要 10 位；不修改密码请留空');return;}
    if(!['ADMIN','FINANCE','OPS','SALES'].includes(f.role)){vm.notify('请选择有效的用户角色');return;}
    try{
      const saved=await rpc('crm_upsert_user',{p_token:token,p_user_id:f.id||null,p_name:f.name,p_username:f.username,p_password:f.password,p_role:f.role,p_enabled:f.enabled!==false});
      if(String(saved?.id||'')===String(vm.currentUser?.id||''))vm.currentUser={...vm.currentUser,...saved};
      await loadUsers();
      vm.showUserModal=false;
      vm.logAudit('保存用户权限',`${saved?.name||f.name} · ${vm.roleLabel(saved?.role||f.role)}`);
      vm.persist();routeFromHash();
      vm.notify('用户权限已保存到服务器');
    }catch(e){vm.notify(e?.message||'用户保存失败');}
  };
  vm.deleteAuthUser=(user)=>{
    if(vm.currentUser?.role!=='ADMIN'){vm.notify('只有管理员可以删除用户');return;}
    if(!vm.canDeleteAuthUser(user)){vm.notify(String(user?.id)===String(vm.currentUser?.id)?'当前正在登录的账号不能删除':'系统至少需要保留一个启用状态的管理员账号');return;}
    vm.askConfirm({title:'删除系统用户',message:`确定删除用户【${user.name}】吗？删除后该账号将无法登录。`,confirmText:'确认删除'},async()=>{
      try{await rpc('crm_delete_user',{p_token:token,p_user_id:user.id});await loadUsers();vm.logAudit('删除系统用户',`${user.name} · ${vm.roleLabel(user.role)}`);vm.persist();vm.notify('用户已从服务器删除');}
      catch(e){vm.notify(e?.message||'用户删除失败');}
    });
  };

  function applyBusinessBackup(p){
    if(!p||!Array.isArray(p.clients))throw new Error('无效备份');
    vm.clients=p.clients.map(c=>vm.normalizeClient(c));
    vm.migrateLegacyAccountSpendRecords();
    vm.standaloneAlerts=(p.standaloneAlerts||[]).map(a=>vm.normalizeStandaloneAlert(a));
    vm.reminderTypes=vm.normalizeReminderTypes(p.reminderTypes||vm.defaultReminderTypes());
    vm.dismissedAlerts=p.dismissedAlerts||[];vm.leads=p.leads||[];
    vm.openingProviders=(p.openingProviders||[]).map(x=>vm.normalizeOpeningProvider(x));vm.openingDeals=p.openingDeals||[];vm.migrateOpeningDeals();
    vm.financeActualRebates=vm.normalizeFinanceActualRebates(p.financeActualRebates||[]);
    vm.financeReceivables=(p.financeReceivables||[]).map(r=>vm.normalizeReceivable(r));
    vm.financeCosts=(p.financeCosts||[]).map(c=>vm.normalizeFinanceCost(c));
    vm.financeReconciliations=(p.financeReconciliations||[]).map(r=>({...r,status:r.status||'CONFIRMED'}));
    vm.financeMonthLocks=p.financeMonthLocks||{};vm.financeMonthSnapshots=p.financeMonthSnapshots||{};
    vm.restoreSopProgress(p.sopProgress||{});vm.mediaTools=(p.mediaTools||[]).map(t=>vm.normalizeMediaTool(t));
    if(Array.isArray(p.auditLogs))vm.auditLogs=p.auditLogs;
    vm.migrateLegacyActualRebatesToReconciliations();vm.ensureAutomaticReceivables({silent:true});vm.ensureAutomaticAssetCosts({month:vm.localDateKey().slice(0,7),silent:true});vm.ensureAutomaticOpeningFeeCosts();vm.ensureReceivableLinkedCosts();vm.ensureFinanceSnapshotsForLocks();
    syncSelections();routeFromHash();vm.persist();
  }
  vm.createBackupSnapshot=(notifyUser=false)=>{
    const snap={id:vm.accountUid('backup'),name:`数据快照 ${vm.localDateKey()} ${new Date().toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit'})}`,backupDate:vm.localDateKey(),createdAt:new Date().toISOString(),payload:sanitizedBackupPayload()};
    vm.backupSnapshots.unshift(snap);vm.backupSnapshots=vm.backupSnapshots.slice(0,5);vm.persist();vm.updateStorageUsage();
    if(notifyUser){vm.logAudit('创建数据快照',snap.name);vm.persist();vm.notify('已创建云端数据快照');}
    return snap;
  };
  vm.deleteBackupSnapshot=(snap)=>{
    if(vm.currentUser?.role!=='ADMIN'){vm.notify('只有管理员可以删除快照');return;}
    vm.askConfirm({title:'删除数据快照',message:`确定删除【${snap.name}】吗？删除后无法通过该快照恢复历史数据。`,confirmText:'删除快照'},()=>{vm.backupSnapshots=vm.backupSnapshots.filter(s=>String(s.id)!==String(snap.id));vm.logAudit('删除数据快照',snap.name);vm.persist();vm.notify('云端快照已删除');});
  };
  vm.restoreBackupSnapshot=(snap)=>{
    if(vm.currentUser?.role!=='ADMIN'){vm.notify('只有管理员可以恢复快照');return;}
    vm.askConfirm({title:'恢复数据快照',message:`确定恢复【${snap.name}】吗？当前业务数据会先自动创建保护快照。`,confirmText:'确认恢复',tone:'warning'},()=>{try{vm.createBackupSnapshot(false);applyBusinessBackup(snap.payload);vm.logAudit('恢复数据快照',snap.name);vm.persist();vm.notify('数据快照已恢复并同步云端');}catch(e){vm.notify(e?.message||'快照恢复失败');}});
  };
  vm.downloadFullBackup=()=>{
    const p=sanitizedBackupPayload(),blob=new Blob([JSON.stringify(p,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');
    a.href=url;a.download=`growth-ops-backup-${vm.localDateKey()}.json`;document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(url);vm.logAudit('导出全量备份',a.download);vm.persist();vm.notify('业务数据备份已导出');
  };
  vm.importFullBackup=(event)=>{
    if(vm.currentUser?.role!=='ADMIN'){vm.notify('只有管理员可以导入备份');event.target.value='';return;}
    const file=event.target.files?.[0];event.target.value='';if(!file)return;
    const reader=new FileReader();reader.onload=()=>{try{const p=JSON.parse(String(reader.result||''));if(!Array.isArray(p.clients))throw new Error('无效备份文件');vm.askConfirm({title:'导入全量备份',message:'导入会覆盖当前业务数据；系统会先创建保护快照。服务器登录账号与权限不会被备份文件覆盖。',confirmText:'确认导入',tone:'warning'},()=>{try{vm.createBackupSnapshot(false);applyBusinessBackup(p);vm.logAudit('导入全量备份',file.name);vm.persist();vm.notify('备份已导入并同步云端');}catch(e){vm.notify(e?.message||'备份导入失败');}});}catch(e){vm.notify(e?.message||'无法读取备份文件');}};reader.readAsText(file,'utf-8');
  };

  vm.login=async()=>{try{const d=await rpc('crm_login',{p_username:String(vm.loginForm.username||'').trim(),p_password:String(vm.loginForm.password||'')});await enter(d);vm.logAudit('登录系统',`${vm.currentUser?.name||''} · ${vm.roleLabel(vm.currentUser?.role)}`);vm.persist();vm.notify('已连接 Supabase 云端数据');}catch(e){vm.notify(e?.message||'账号或密码错误');}};
  vm.logout=async()=>{const old=vm.currentUser;if(old){vm.logAudit('退出系统',old.name||'');try{await saveNow();}catch{}}try{if(token)await rpc('crm_logout',{p_token:token});}catch{}token='';revision=0;localStorage.removeItem(TOKEN_KEY);emptyState();vm.currentUser=null;vm.loginForm={username:'',password:''};vm.currentPage='dashboard';};
  async function boot(){
    emptyState();vm.currentUser=null;
    try{await rpc('crm_public_status');if(token){try{const d=await rpc('crm_load_state',{p_token:token});await enter(d);return;}catch{token='';localStorage.removeItem(TOKEN_KEY);}}}
    catch(e){vm.notify(`Supabase 连接失败：${e.message}`);}
  }
  window.__growthOpsCloud={rpc,saveNow,loadUsers};
  boot();
})();
// Production rebuild marker: cloud-v2 lifecycle verified.
