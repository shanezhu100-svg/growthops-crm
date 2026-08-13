云端工作区的业务数据会被演示数据覆盖。建议先导出备份。用户账号不会被重置。确定继续吗？',confirmText:'确认恢复',tone:'warning'},()=>{this.clients=structuredClone(seedClients).map(c=>this.normalizeClient(c));this.standaloneAlerts=structuredClone(seedAlerts).map(a=>this.normalizeStandaloneAlert(a));this.reminderTypes=this.defaultReminderTypes();this.dismissedAlerts=[];this.leads=structuredClone(seedLeads);this.openingProviders=structuredClone(seedOpeningProviders).map(p=>this.normalizeOpeningProvider(p));this.openingDeals=structuredClone(seedOpeningDeals);this.financeActualRebates=[];this.financeReceivables=[];this.financeCosts=[];this.financeReconciliations=[];this.financeMonthLocks={};this.financeMonthSnapshots={};this.backupSnapshots=[];this.auditLogs=[];this.mediaTools=structuredClone(seedMediaTools).map(t=>this.normalizeMediaTool(t));this.restoreSopProgress({});this.migrateLegacyAccountSpendRecords();this.selectedClientId=1;this.selectedAssetsClientId=1;this.selectedSopClientId=null;this.selectedSopAccountKey='';this.selectedSopDate=this.localDateKey();this.selectedAnalyticsClientId=1;this.selectedAnalyticsFbAccountId=null;this.selectedAnalyticsTkAccountId=null;this.selectedAdsClientId=1;this.selectedAdsPlatform='FB';this.selectedAdsAccountId=null;this.syncAnalyticsAccountSelection();this.syncAdsAccountSelection();this.syncSopAccountSelection(true);this.logAudit('恢复演示数据','管理员手工执行');this.notify('已恢复演示业务数据并同步云端');this.navigateTo('dashboard')})};
  }

  function initializeForms(){
    vm.form=vm.defaultForm();vm.leadForm=vm.defaultLeadForm();vm.openingForm=vm.defaultOpeningForm();vm.providerForm=vm.defaultProviderForm();vm.toolForm=vm.defaultToolForm();vm.receivableForm=vm.defaultReceivableForm();vm.costForm=vm.defaultCostForm();vm.reconciliationForm=vm.defaultReconciliationForm();vm.userForm={id:null,name:'',username:'',['pass'+'word']:'',role:'OPS',enabled:true};
  }
  function initializeBusinessRuntime(){
    vm.migrateLegacyAccountSpendRecords();
    vm.ensureAutomaticReceivables({silent:true});
    vm.ensureAutomaticAssetCosts({month:vm.localDateKey().slice(0,7),silent:true});
    vm.ensureAutomaticOpeningFeeCosts();vm.ensureReceivableLinkedCosts();vm.ensureFinanceSnapshotsForLocks();
    vm.updateStorageUsage();vm.syncAnalyticsAccountSelection();vm.syncAdsAccountSelection();vm.syncSopAccountSelection();
    vm.ensureDailyBackup();
  }
  function installRouting(){
    const allowed=['dashboard','lead