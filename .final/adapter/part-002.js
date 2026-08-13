filter(a=>a.typeKey!=='TOOL').map(a=>vm.normalizeStandaloneAlert(a));
    vm.reminderTypes=vm.normalizeReminderTypes(Array.isArray(st.reminderTypes)&&st.reminderTypes.length?st.reminderTypes:vm.defaultReminderTypes());
    vm.dismissedAlerts=Array.isArray(st.dismissedAlerts)?st.dismissedAlerts:[];
    vm.leads=Array.isArray(st.leads)?st.leads:legacyLeads(legacy);
    vm.openingProviders=(Array.isArray(st.openingProviders)?st.openingProviders:[]).map(p=>vm.normalizeOpeningProvider(p));
    vm.openingDeals=Array.isArray(st.openingDeals)?st.openingDeals:[];
    vm.migrateOpeningDeals();
    vm.financeActualRebates=vm.normalizeFinanceActualRebates(Array.isArray(st.financeActualRebates)?st.financeActualRebates:[]);
    vm.financeReceivables=(Array.isArray(st.financeReceivables)?st.financeReceivables:[]).map(r=>vm.normalizeReceivable(r));
    vm.financeCosts=(Array.isArray(st.financeCosts)?st.financeCosts:[]).map(c=>vm.normalizeFinanceCost(c));
    vm.financeReconciliations=(Array.isArray(st.financeReconciliations)?st.financeReconciliations:[]).map(r=>({...r,status:r.status||'CONFIRMED'}));
    vm.migrateLegacyActualRebatesToReconciliations();
    vm.financeMonthLocks=st.financeMonthLocks&&typeof st.financeMonthLocks==='object'?st.financeMonthLocks:{};
    vm.financeMonthSnapshots=st.financeMonthSnapshots&&typeof st.financeMonthSnapshots==='object'?st.financeMonthSnapshots:{};
    vm.backupSnapshots=Array.isArray(st.backupSnapshots)?st.backupSnapshots:[];
    vm.auditLogs=Array.isArray(st.auditLogs)?st.auditLogs:[];
    vm.mediaTools=(Array.isArray(st.mediaTools)?st.mediaTools:[]).map(t=>vm.normalizeMediaTool(t));
    vm.restoreSopProgress(st.sopProgressStore&&typeof st.sopProgressStore==='object'?st.sopProgressStore:{});
    const first=vm.clients.find(c=>!c.archived)||vm.clients[0]||null;
    if(first){
      if(!vm.clients.some(c=>String(c.id)===String(vm.selectedClientId)))vm.selectedClientId=first.id;
      if(!vm.clients.some(c=>String(c.id)===String(vm.selectedAssetsClientId)))vm.selectedAssetsClientId=first.id;
      if(!vm.clients.some(c=>String(c.id)===String(vm.selectedAnalyticsClientId)))vm.selectedAnalyticsClientId=first.id;
      if(!vm.clients.some(c=>String(c.id)===String(vm.selectedAdsClientId)))vm.selectedAdsClientId=first.id;
    }else{
      vm.selectedClientId=null;vm.selectedAssetsClientId=null;vm.selectedSopClientId=null;vm.selectedAnalyticsClientId=0;vm.selectedAdsClientId=0;
    }
    vm.updateStorageUsage();
  }

  async function flush(){
    if(saving||!token||!vm.currentUser||conflict)return;
    saving=true;
    try{
      while(pendingState&&token&&vm.currentUser&&!conflict){
        const payload=pendingState;pendingState=null;
        try{
          const d=await rpc('crm_save_state',{p_token:token,p_state:payload,p_expected_revision:revision});
          revision=Number(d?.revision??revision+1);
        }catch(e){
          console.error(e);
          pendingState=payload;
          if(String(e.message||'').includes('CL