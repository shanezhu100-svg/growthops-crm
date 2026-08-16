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
  const invokeLegacyClientNavigate=page=>{
    const sourcePage=vm.currentPage;
    if(sourcePage)rememberPageScroll(sourcePage);
    const targetTop=getPageScroll(page);
    const originalScrollTo=window.scrollTo;
    window.scrollTo=()=>writeScrollTop(targetTop);
    try{
      if(typeof vm.navigateTo==='function')vm.navigateTo(page);
      else{
        vm.currentPage=page;
        setPageUrl(page);
      }
    }catch(error){
      console.error(error);
      vm.notify?.('页面切换失败，请刷新页面后重试');
      return false;
    }finally{
      window.scrollTo=originalScrollTo;
    }
    vm.mobileMenuOpen=false;
    try{vm.$forceUpdate?.()}catch{}
    const settle=()=>restorePageScrollInstant(page);
    if(typeof vm.$nextTick==='function')vm.$nextTick(settle);
    else queueMicrotask(settle);
    return true;
  };
  const clientIdForTableRow=button=>{
    const row=button?.closest('tr');
    const rows=row?.parentElement?[...row.parentElement.children].filter(node=>node.tagName==='TR'):[];
    const index=rows.indexOf(row);
    return index>=0?(vm.filteredClients?.[index]?.id??null):null;
  };
  const clientIdForMobileDetailButton=button=>{
    const buttons=[...document.querySelectorAll('button')].filter(node=>text(node)==='查看客户详情');
    const index=buttons.indexOf(button);
    return index>=0?(vm.filteredClients?.[index]?.id??null):null;
  };
  const openClientDetailNative=(button,mobile=false)=>{
    const clientId=mobile?clientIdForMobileDetailButton(button):clientIdForTableRow(button);
    if(clientId==null){vm.notify?.('客户详情未加载，请刷新页面');return}
    const sourcePage=vm.currentPage;
    if(sourcePage)rememberPageScroll(sourcePage);
    pageScrollPositions['client-detail']=0;
    const originalScrollTo=window.scrollTo;
    window.scrollTo=()=>writeScrollTop(0);
    try{
      if(typeof vm.openClientDetail==='function')vm.openClientDetail(clientId);
      else{
        vm.selectedClientId=clientId;
        if(typeof vm.navigateTo==='function')vm.navigateTo('client-detail');
        else vm.currentPage='client-detail';
      }
    }catch(error){
      console.error(error);
      vm.notify?.('客户详情打开失败，请刷新页面后重试');
      return;
    }finally{
      window.scrollTo=originalScrollTo;
    }
    if(vm.selectedClientId==null)vm.selectedClientId=clientId;
    if(vm.currentPage!=='client-detail')vm.currentPage='client-detail';
    setPageUrl('client-detail');
    try{vm.$forceUpdate?.()}catch{}
    const settle=()=>restorePageScrollInstant('client-detail');
    if(typeof vm.$nextTick==='function')vm.$nextTick(settle);
    else queueMicrotask(settle);
  };
  const readScrollTop=()=>{
""",
'legacy client navigation helpers'
)

replace_once(
"""    if(vm.currentPage==='client-form'){
""",
"""    if(vm.currentPage==='clients'){
      document.querySelectorAll('tbody tr').forEach(row=>{
        const firstButton=row.querySelector('td:first-child button');
        const detailButton=[...row.querySelectorAll('button')].find(button=>text(button)==='详情');
        if(firstButton)bind(firstButton,'client-detail-name-open',()=>openClientDetailNative(firstButton,false));
        if(detailButton)bind(detailButton,'client-detail-open',()=>openClientDetailNative(detailButton,false));
      });
      document.querySelectorAll('button').forEach(button=>{
        if(text(button)==='查看客户详情')bind(button,'client-detail-mobile-open',()=>openClientDetailNative(button,true));
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
          invokeLegacyClientNavigate(vm.form?.id?'client-detail':'clients');
        });
""",
'client form back/cancel binding'
)

replace_once(
"""version:'native-action-bridge-v15-page-scroll-memory'""",
"""version:'native-action-bridge-v17-legacy-method-navigation'""",
'UI action bridge version'
)

path.write_text(text,encoding='utf-8')
print('UI_CLIENT_NAVIGATION_FINALIZE_OK: bridge='+hashlib.sha256(path.read_bytes()).hexdigest())
