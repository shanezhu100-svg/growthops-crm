from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
index_path=root/'dist'/'index.html'
html=index_path.read_text(encoding='utf-8')

old_method="    openClientDetail(id){this.selectedClientId=id;this.credentialsVisible=false;this.resetAssetPager('detail');this.navigateTo('client-detail')},"
new_method="""    openClientDetail(id){
      const source=String(this.currentPage||'');
      this.clientDetailReturnPage=(source&&source!=='client-detail'&&source!=='client-form'&&this.canViewPage(source))?source:'clients';
      if(this.clientDetailReturnPage==='assets')this.selectedAssetsClientId=id;
      this.selectedClientId=id;
      this.credentialsVisible=false;
      this.resetAssetPager('detail');
      this.navigateTo('client-detail');
    },
    returnFromClientDetail(){
      const source=String(this.clientDetailReturnPage||'');
      const target=(source&&source!=='client-detail'&&source!=='client-form'&&this.canViewPage(source))?source:'clients';
      if(target==='assets'&&this.selectedClientId!==null&&this.selectedClientId!==undefined)this.selectedAssetsClientId=this.selectedClientId;
      this.clientDetailReturnPage='';
      this.navigateTo(target);
    },"""
if html.count(old_method)!=1:
    raise SystemExit(f'Unexpected openClientDetail method count: {html.count(old_method)}')
html=html.replace(old_method,new_method,1)

old_back='<button @click="navigateTo(\'clients\')" class="w-10 h-10 rounded-xl border border-slate-200 bg-white"><i class="fa-solid fa-arrow-left"></i></button>'
new_back='<button type="button" @click="returnFromClientDetail()" class="w-10 h-10 rounded-xl border border-slate-200 bg-white" title="返回上一来源页面"><i class="fa-solid fa-arrow-left"></i></button>'
if html.count(old_back)!=1:
    raise SystemExit(f'Unexpected client-detail fixed back button count: {html.count(old_back)}')
html=html.replace(old_back,new_back,1)

index_path.write_text(html,encoding='utf-8')
print('CLIENT_DETAIL_RETURN_FINALIZE_OK: index='+hashlib.sha256(index_path.read_bytes()).hexdigest())
