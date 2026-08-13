(()=>{
  const SUPABASE_URL='__SUPABASE_URL__';
  const API_KEY='__SUPABASE_KEY__';
  const TOKEN_KEY='growthops_crm_token_v2';
  const vm=window.__CRM_APP__;
  if(!vm){console.error('GrowthOps cloud adapter: Vue app not found');return;}

  let token=localStorage.getItem(TOKEN_KEY)||'';
  let revision=0;
  let pendingState=null;
  let saving=false;
  let conflict=false;

  async function rpc(name,body={}){
    const r=await fetch(`${SUPABASE_URL}/rest/v1/rpc/${name}`,{
      method:'POST',
      headers:{apikey:API_KEY,'Content-Type':'application/json'},
      body:JSON.stringify(body)
    });
    let data=null;try{data=await r.json()}catch{}
    if(!r.ok)throw new Error(data?.message||data?.hint||`请求失败 ${r.status}`);
    return data;
  }
  const clone=v=>JSON.parse(JSON.stringify(v??null));
  const platform=v=>{const p=String(v||'');if(p.includes('TikTok')&&p.includes('Facebook'))return'FB+TK';if(p.includes('TikTok'))return'TK';if(p.includes('Facebook'))return'FB';return['FB','TK','FB+TK'].includes(p)?p:'FB+TK'};
  const legacyLeadStage=s=>s==='已流失'?'LOST':s==='高意向'?'QUALIFIED':s==='待跟进'?'CONTACTED':'NEW';

  function legacyClients(rows){
    return (rows||[]).filter(c=>c.status==='合作中').map(c=>vm.normalizeClient({...vm.defaultForm(),id:c.id||Date.now(),name:c.name||'未命名客户',product:c.note||'',project:'',platform:platform(c.platform),status:'ACTIVE'}));
  }
  function legacyLeads(rows){
    return (rows||[]).filter(c=>c.status!=='合作中').map(c=>({id:c.id||vm.accountUid('lead'),company:c.name||'未命名客户',contact:c.contact||'',contactInfo:c.phone||'',source:'旧版客户迁移',platformInterest:platform(c.platform),budgetCurrency:'USD',expectedBudget:0,quoteCurrency:'USD',adQuote:0,stage:legacyLeadStage(c.status),nextFollowUp:'',owner:'',notes:c.note||'',createdAt:String(c.createdAt||'').slice(0,10)||vm.localDateKey(),convertedClientId:null,convertedAt:''}));
  }

  function statePayload(){
    return {
      schemaVersion:'growth-ops-cloud-2026.08-1to1-v1',
      clients:vm.clients,
      standaloneAlerts:vm.standaloneAlerts,
      reminderTypes:vm.reminderTypes,
      dismissedAlerts:vm.dismissedAlerts,
      leads:vm.leads,
      openingProviders:vm.openingProviders,
      openingDeals:vm.openingDeals,
      financeActualRebates:vm.financeActualRebates,
      financeReceivables:vm.financeReceivables,
      financeCosts:vm.financeCosts,
      financeReconciliations:vm.financeReconciliations,
      financeMonthLocks:vm.financeMonthLocks,
      financeMonthSnapshots:vm.financeMonthSnapshots,
      backupSnapshots:vm.backupSnapshots,
      auditLogs:vm.auditLogs,
      mediaTools:vm.mediaTools,
      sopProgressStore:vm.collectSopProgress()
    };
  }

  function hydrate(st={}){
    st=st&&typeof st==='object'?st:{};
    const legacy=Array.isArray(st.customers)?st.customers:[];
    vm.clients=(Array.isArray(st.clients)?st.clients:legacyClients(legacy)).map(c=>vm.normalizeClient(c));
    vm.standaloneAlerts=(Array.isArray(st.standaloneAlerts)?st.standaloneAlerts:[]).