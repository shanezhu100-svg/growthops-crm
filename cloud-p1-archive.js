
(()=>{
  'use strict';
  const INSTALLED='__GROWTHOPS_P1_ARCHIVE_STATUS_INSTALLED__';
  const PREVIOUS_STATUS_KEY='p1ArchivePreviousStatus';
  const vmRef=()=>window.__growthOpsVm||window.CRM?.state||window.CRM?.methods;
  const statusValue=value=>typeof value==='string'&&value.trim()?value.trim():'';

  function install(){
    const vm=vmRef();
    if(!vm||vm[INSTALLED])return false;
    if(typeof vm.archiveClient!=='function'||typeof vm.restoreClient!=='function')return false;
    Object.defineProperty(vm,INSTALLED,{value:true,configurable:false});

    vm.archiveClient=function(client){
      if(!client||client.archived)return;
      if(!this.canArchiveClients?.()){
        this.notify?.('当前角色没有归档客户的权限');
        return;
      }
      this.askConfirm?.({
        title:'归档客户',
        message:`确定归档客户【${client.name}】吗？\n\n归档后历史广告、开户、财务和回款数据都会保留，但客户不再参与当前运营预警。`,
        confirmText:'确认归档',
        tone:'warning'
      },()=>{
        const previous=statusValue(client.status);
        if(previous)client[PREVIOUS_STATUS_KEY]=previous;
        else delete client[PREVIOUS_STATUS_KEY];
        client.archived=true;
        client.archivedAt=new Date().toISOString();
        client.status='PAUSED';
        this.persist?.();
        this.logAudit?.('归档客户',client.name);
        this.notify?.(`客户【${client.name}】已归档`);
      });
    };

    vm.restoreClient=function(client){
      if(!client?.archived)return;
      if(!this.canArchiveClients?.()){
        this.notify?.('当前角色没有恢复客户的权限');
        return;
      }
      this.askConfirm?.({title:'恢复归档客户',message:`确定恢复客户【${client.name}】吗？`,confirmText:'确认恢复',tone:'warning'},()=>{
        const previous=statusValue(client[PREVIOUS_STATUS_KEY]);
        client.archived=false;
        client.archivedAt='';
        client.status=previous||'ACTIVE';
        delete client[PREVIOUS_STATUS_KEY];
        this.persist?.();
        this.logAudit?.('恢复归档客户',client.name);
        this.notify?.(previous?`客户已恢复，状态已恢复为 ${previous}`:'客户已恢复到当前合作客户');
      });
    };

    window.__GROWTHOPS_P1_ARCHIVE_STATUS__={installed:true,field:PREVIOUS_STATUS_KEY,semantics:'administrative-archive-not-billing-pause'};
    return true;
  }

  if(!install())window.addEventListener('crm-ready',install,{once:false});
})();
