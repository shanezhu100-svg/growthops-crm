from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
index_path=root/'dist'/'index.html'
html=index_path.read_text(encoding='utf-8')

old_method="    openClientDetail(id){this.selectedClientId=id;this.credentialsVisible=false;this.resetAssetPager('detail');this.navigateTo('client-detail')},"
new_method="""    openClientDetail(id,sourcePage=''){
      const allowedSources=new Set(['dashboard','leads','clients','assets','sop','analytics','ads','opening','finance','alerts','settings']);
      const requestedSource=String(sourcePage||'').trim();
      const currentSource=String(this.currentPage||'').trim();
      const source=allowedSources.has(requestedSource)?requestedSource:(allowedSources.has(currentSource)?currentSource:'clients');
      this.clientDetailReturnPage=source;
      try{sessionStorage.setItem('growthops_client_detail_return_page',source)}catch(_e){}
      if(source==='assets')this.selectedAssetsClientId=id;
      this.selectedClientId=id;
      this.credentialsVisible=false;
      this.resetAssetPager('detail');
      this.navigateTo('client-detail');
    },
    returnFromClientDetail(){
      const allowedSources=new Set(['dashboard','leads','clients','assets','sop','analytics','ads','opening','finance','alerts','settings']);
      let storedSource='';
      try{storedSource=String(sessionStorage.getItem('growthops_client_detail_return_page')||'').trim()}catch(_e){}
      const memorySource=String(this.clientDetailReturnPage||'').trim();
      const source=allowedSources.has(storedSource)?storedSource:(allowedSources.has(memorySource)?memorySource:'clients');
      if(source==='assets'&&this.selectedClientId!==null&&this.selectedClientId!==undefined)this.selectedAssetsClientId=this.selectedClientId;
      this.clientDetailReturnPage='';
      try{sessionStorage.removeItem('growthops_client_detail_return_page')}catch(_e){}
      this.navigateTo(source);
    },"""
if html.count(old_method)!=1:
    raise SystemExit(f'Unexpected openClientDetail method count: {html.count(old_method)}')
html=html.replace(old_method,new_method,1)

old_back='<button @click="navigateTo(\'clients\')" class="w-10 h-10 rounded-xl border border-slate-200 bg-white"><i class="fa-solid fa-arrow-left"></i></button>'
new_back='<button type="button" @click="returnFromClientDetail()" class="w-10 h-10 rounded-xl border border-slate-200 bg-white" title="返回上一来源页面"><i class="fa-solid fa-arrow-left"></i></button>'
if html.count(old_back)!=1:
    raise SystemExit(f'Unexpected client-detail fixed back button count: {html.count(old_back)}')
html=html.replace(old_back,new_back,1)

old_assets_button='''<button v-if="selectedAssetsClient" @click="openClientDetail(selectedAssetsClient.id)" class="h-10 px-4 rounded-xl border border-slate-200 bg-white text-xs font-bold hover:bg-slate-50 transition">
                <i class="fa-regular fa-folder-open mr-1.5"></i>客户详情
              </button>'''
new_assets_button='''<button v-if="selectedAssetsClient" @click="openClientDetail(selectedAssetsClient.id,'assets')" class="h-10 px-4 rounded-xl border border-slate-200 bg-white text-xs font-bold hover:bg-slate-50 transition">
                <i class="fa-regular fa-folder-open mr-1.5"></i>客户详情
              </button>'''
if html.count(old_assets_button)!=1:
    raise SystemExit(f'Unexpected account-assets client detail button count: {html.count(old_assets_button)}')
html=html.replace(old_assets_button,new_assets_button,1)

index_path.write_text(html,encoding='utf-8')
print('CLIENT_DETAIL_RETURN_FINALIZE_OK: index='+hashlib.sha256(index_path.read_bytes()).hexdigest())
