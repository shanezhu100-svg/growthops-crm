from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
path=root/'dist'/'cloud-ui-action-bridge.js'
text=path.read_text(encoding='utf-8')

def replace_once(old,new,label):
    global text
    count=text.count(old)
    if count!=1:
        raise SystemExit(f'Unexpected {label} count: {count}')
    text=text.replace(old,new,1)

replace_once(
"""  const setPageUrl=page=>{
    try{
      const next=new URL(window.location.href);
      next.hash=page;
      window.history.replaceState(window.history.state,'',next.toString());
    }catch{}
  };
  const readScrollTop=()=>{
""",
"""  const setPageUrl=page=>{
    try{
      const next=new URL(window.location.href);
      next.hash=page;
      window.history.replaceState(window.history.state,'',next.toString());
    }catch{}
  };
  const directClientNavigate=page=>{
    vm.currentPage=page;
    vm.mobileMenuOpen=false;
    setPageUrl(page);
  };
  const clientIdForDetailButton=button=>{
    const label=text(button);
    if(label==='详情'){
      const row=button.closest('tr');
      const rows=row?.parentElement?[...row.parentElement.children].filter(node=>node.tagName==='TR'):[];
      const index=rows.indexOf(row);
      return index>=0?(vm.filteredClients?.[index]?.id??null):null;
    }
    if(label==='查看客户详情'){
      const buttons=[...document.querySelectorAll('button')].filter(node=>text(node)==='查看客户详情');
      const index=buttons.indexOf(button);
      return index>=0?(vm.filteredClients?.[index]?.id??null):null;
    }
    return null;
  };
  const openClientDetailNative=button=>{
    const clientId=clientIdForDetailButton(button);
    if(clientId==null){vm.notify?.('客户详情未加载，请刷新页面');return}
    const originalNavigate=vm.navigateTo;
    if(typeof originalNavigate==='function')vm.navigateTo=()=>true;
    try{
      if(typeof vm.openClientDetail==='function')vm.openClientDetail(clientId);
      else vm.selectedClientId=clientId;
    }catch(error){
      console.error(error);
      vm.notify?.('客户详情打开失败，请刷新页面后重试');
      return;
    }finally{
      if(vm.navigateTo!==originalNavigate)vm.navigateTo=originalNavigate;
    }
    if(vm.selectedClientId==null)vm.selectedClientId=clientId;
    directClientNavigate('client-detail');
  };
  const readScrollTop=()=>{
""",
'direct client navigation helpers'
)

replace_once(
"""    if(vm.currentPage==='client-form'){
""",
"""    if(vm.currentPage==='clients'){
      document.querySelectorAll('button').forEach(button=>{
        const label=text(button);
        if(label==='详情'||label==='查看客户详情')bind(button,'client-detail-open',()=>openClientDetailNative(button));
      });
    }
    if(vm.currentPage==='client-form'){
""",
'client detail native binding'
)

replace_once(
"""        if(label==='取消'||icon)bind(button,'client-form-back',()=>navigateWithPageScroll(vm.form?.id?'client-detail':'clients'));
""",
"""        if(label==='取消'||icon)bind(button,'client-form-back',()=>{
          vm.formDirty=false;
          directClientNavigate(vm.form?.id?'client-detail':'clients');
        });
""",
'client form back/cancel binding'
)

replace_once(
"""version:'native-action-bridge-v15-page-scroll-memory'""",
"""version:'native-action-bridge-v16-client-native-navigation'""",
'UI action bridge version'
)

path.write_text(text,encoding='utf-8')
print('UI_CLIENT_NAVIGATION_FINALIZE_OK: bridge='+hashlib.sha256(path.read_bytes()).hexdigest())
