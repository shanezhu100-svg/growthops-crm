OUD_REVISION_CONFLICT')){
            conflict=true;
            vm.notify('云端数据已被其他成员更新，请刷新页面加载最新版后再操作');
          }else vm.notify('云端保存失败：'+(e.message||e));
          break;
        }
      }
    }finally{saving=false;}
  }

  async function loadUsers(){
    if(!vm.currentUser){vm.authUsers=[];return;}
    if(vm.currentUser.role!=='ADMIN'){vm.authUsers=[{...vm.currentUser}];return;}
    try{const rows=await rpc('crm_list_users',{p_token:token});vm.authUsers=Array.isArray(rows)?rows:[];}
    catch(e){console.error(e);vm.authUsers=[{...vm.currentUser}];}
  }

  function installOverrides(){
    vm.persist=function(){
      if(!token||!this.currentUser||conflict)return false;
      try{pendingState=clone(statePayload());this.updateStorageUsage();flush();return true;}
      catch(e){console.error(e);this.notify('云端数据准备失败，请刷新页面后重试');return false;}
    };
    vm.updateStorageUsage=function(){try{this.storageUsageBytes=new Blob([JSON.stringify(statePayload())]).size;return this.storageUsageBytes}catch{this.storageUsageBytes=0;return 0}};
    vm.logAudit=function(action,detail=''){this.auditLogs.unshift({id:this.accountUid('log'),at:new Date().toISOString(),user:this.currentUser?.name||'系统',action,detail});this.auditLogs=this.auditLogs.slice(0,200);if(this.currentUser)this.persist()};
    vm.saveSopProgress=function(){const key=this.sopProgressKey();if(!key)return;localStorage.setItem(key,JSON.stringify(this.sopChecked));this.persist()};
    vm.createBackupSnapshot=function(notifyUser=false){const payload=this.collectBackupPayload(),backupDate=this.localDateKey(),snap={id:this.accountUid('backup'),name:`数据快照 ${backupDate} ${new Date().toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit'})}`,backupDate,createdAt:new Date().toISOString(),payload};this.backupSnapshots.unshift(snap);this.backupSnapshots=this.backupSnapshots.slice(0,5);this.persist();if(notifyUser){this.logAudit('创建数据快照',snap.name);this.notify('已创建全量云端数据快照')}return snap};
    vm.deleteBackupSnapshot=function(snap){if(this.currentUser?.role!=='ADMIN'){this.notify('只有管理员可以删除数据快照');return}if(!snap?.id)return;this.askConfirm({title:'删除数据快照',message:`确定删除【${snap.name}】吗？\n删除后无法通过该快照恢复历史数据。`,confirmText:'删除快照'},()=>{this.backupSnapshots=this.backupSnapshots.filter(s=>String(s.id)!==String(snap.id));this.logAudit('删除数据快照',snap.name);this.notify('数据快照已删除')})};
    vm.collectBackupPayload=function(){return{version:'growth-ops-2026.08-cloud-1to1-v1',exportedAt:new Date().toISOString(),clients:this.clients,standaloneAlerts:this.standaloneAlerts,reminderTypes:this.reminderTypes,dismissedAlerts:this.dismissedAlerts,leads:this.leads,openingProviders:this.openingProviders,openingDeals:this.openingDeals,financeActualRebates:this.financeActualRebates,financeReceivables:this.financeReceivables,financeCosts:this.financeCosts,financeReconciliations:this.financeReconciliations,financeMonthLocks:this.financeMonthLocks,financeMonthSnapshots:this.financeMonthSnapshots,sopProgress:this.collectSopProgress(),m