(()=>{
  'use strict';
  const vm=window.__growthOpsVm;
  if(!vm)return;
  const VERSION='client-scroll-anchor-v19-row-position';
  let anchor=null;

  const text=el=>String(el?.textContent||'').replace(/\s+/g,' ').trim();
  const documentScroller=()=>document.scrollingElement||document.documentElement||document.body;
  const normalizeScrollTarget=target=>{
    if(target===window||target===document||target===document.documentElement||target===document.body)return documentScroller();
    return target instanceof Element?target:null;
  };
  const hasVerticalRange=target=>!!target&&Number(target.scrollHeight||0)>Number(target.clientHeight||0)+1;
  const canOwnVerticalScroll=target=>{
    target=normalizeScrollTarget(target);
    if(!target||!hasVerticalRange(target))return false;
    if(target===documentScroller())return true;
    try{
      const overflowY=getComputedStyle(target).overflowY;
      return overflowY!=='visible'&&overflowY!=='clip';
    }catch{return true}
  };
  const findScrollTarget=node=>{
    let current=node instanceof Element?node:null;
    while(current&&current!==document.body&&current!==document.documentElement){
      if(canOwnVerticalScroll(current))return current;
      current=current.parentElement;
    }
    return documentScroller();
  };
  const readTargetScrollTop=target=>Math.max(0,Number(normalizeScrollTarget(target)?.scrollTop||0));
  const writeTargetScrollTop=(target,top)=>{
    target=normalizeScrollTarget(target);
    if(!target)return;
    const value=Math.max(0,Number(top)||0);
    target.scrollTop=value;
    if(target===documentScroller()){
      if(document.documentElement&&document.documentElement!==target)document.documentElement.scrollTop=value;
      if(document.body&&document.body!==target)document.body.scrollTop=value;
    }
  };
  const isClientDetailOpenButton=button=>{
    if(!button)return false;
    const label=text(button);
    if(label==='详情'||label==='查看客户详情')return true;
    const row=button.closest('tbody tr');
    return !!row&&button===row.querySelector('td:first-child button');
  };
  const rowFingerprint=row=>{
    if(!row)return '';
    const cells=[...row.querySelectorAll('td')].map(cell=>text(cell)).filter(Boolean);
    return cells.length?cells.join('¦'):text(row);
  };
  const rowsNow=()=>[...document.querySelectorAll('tbody tr')].filter(row=>{
    const rect=row.getBoundingClientRect();
    return rect.width>0&&rect.height>0;
  });
  const selectedClient=()=>{
    if(!anchor?.clientId||!Array.isArray(vm.clients))return null;
    return vm.clients.find(client=>String(client?.id??'')===anchor.clientId)||null;
  };
  const stableClientTokens=client=>{
    if(!client||typeof client!=='object')return [];
    const preferred=['name','clientName','customerName','company','companyName','phone','mobile','email','wechat','id'];
    const values=[];
    for(const key of preferred){
      const value=client[key];
      if(value===null||value===undefined)continue;
      const normalized=String(value).replace(/\s+/g,' ').trim();
      if(normalized&&normalized.length<=120&&!values.includes(normalized))values.push(normalized);
    }
    return values;
  };
  const locateAnchorRow=()=>{
    const rows=rowsNow();
    if(!rows.length)return null;
    if(anchor?.fingerprint){
      const exact=rows.find(row=>rowFingerprint(row)===anchor.fingerprint);
      if(exact)return exact;
    }
    const client=selectedClient();
    const tokens=stableClientTokens(client);
    if(tokens.length){
      let best=null,bestScore=0;
      for(const row of rows){
        const value=text(row);
        const score=tokens.reduce((sum,token)=>sum+(value.includes(token)?1:0),0);
        if(score>bestScore){best=row;bestScore=score}
      }
      if(best&&bestScore>0)return best;
    }
    if(Number.isInteger(anchor?.rowIndex)&&anchor.rowIndex>=0&&anchor.rowIndex<rows.length)return rows[anchor.rowIndex];
    return null;
  };
  const captureAnchor=button=>{
    const row=button?.closest?.('tbody tr');
    if(!row)return;
    const rows=rowsNow();
    const target=findScrollTarget(button);
    const rect=row.getBoundingClientRect();
    anchor={
      fingerprint:rowFingerprint(row),
      rowIndex:rows.indexOf(row),
      viewportTop:rect.top,
      viewportLeft:rect.left,
      listScrollTop:readTargetScrollTop(target),
      clientId:null,
      capturedAt:Date.now()
    };
    const captureClientId=()=>{
      if(anchor&&vm.selectedClientId!==null&&vm.selectedClientId!==undefined&&vm.selectedClientId!=='')anchor.clientId=String(vm.selectedClientId);
    };
    queueMicrotask(captureClientId);
    setTimeout(captureClientId,0);
  };
  const applyAnchor=()=>{
    if(!anchor||vm.currentPage!=='clients')return false;
    const row=locateAnchorRow();
    if(!row)return false;
    const target=findScrollTarget(row);
    const rect=row.getBoundingClientRect();
    const delta=rect.top-anchor.viewportTop;
    if(Number.isFinite(delta)&&Math.abs(delta)>0.5)writeTargetScrollTop(target,readTargetScrollTop(target)+delta);
    return true;
  };
  const scheduleAnchorRestore=()=>{
    const run=()=>{try{applyAnchor()}catch(error){console.error(error)}};
    const afterRender=()=>{
      requestAnimationFrame(()=>{
        run();
        setTimeout(run,130);
        setTimeout(run,260);
        setTimeout(run,520);
      });
    };
    if(typeof vm.$nextTick==='function')vm.$nextTick(afterRender);
    else queueMicrotask(afterRender);
  };

  window.addEventListener('pointerdown',event=>{
    if(vm.currentPage!=='clients')return;
    const button=event.target?.closest?.('button');
    if(!isClientDetailOpenButton(button))return;
    captureAnchor(button);
  },true);

  window.addEventListener('click',event=>{
    if(vm.currentPage!=='client-detail'||!anchor)return;
    const button=event.target?.closest?.('button');
    if(!button||!button.querySelector('i.fa-arrow-left'))return;
    scheduleAnchorRestore();
  },true);

  window.__GROWTHOPS_CLIENT_SCROLL_ANCHOR__={
    installed:true,
    version:VERSION,
    restore:()=>applyAnchor(),
    getAnchor:()=>anchor?{...anchor}:null
  };
})();