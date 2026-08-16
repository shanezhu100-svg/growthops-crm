from pathlib import Path
import hashlib

root = Path(__file__).resolve().parent
path = root / 'dist' / 'cloud-security-hotfix.js'
text = path.read_text(encoding='utf-8')

old = '''  function ensureRevealButton(){
    let button=document.getElementById(BUTTON_ID);
    if(!button){
      button=make('button',{
        id:BUTTON_ID,
        type:'button',
        style:'position:fixed;right:18px;bottom:72px;z-index:2147482500;border:0;border-radius:999px;background:#0f172a;color:#fff;padding:10px 14px;box-shadow:0 10px 30px rgba(15,23,42,.2);font:700 13px/1.2 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;cursor:pointer;'
      },'安全查看客户凭证');
      button.addEventListener('click',revealSelectedClient);
      document.body.appendChild(button);
    }

    const visible=vm.currentUser?.role==='ADMIN'&&vm.currentPage==='client-detail'&&vm.selectedClientId!=null;
    button.style.display=visible?'block':'none';
  }
'''

new = '''  function findRevealHost(){
    if(vm.currentPage!=='client-detail')return null;
    const heading=[...document.querySelectorAll('h3')].find(node=>String(node.textContent||'').trim()==='平台资产与账号');
    const titleBlock=heading?.parentElement||null;
    const header=titleBlock?.parentElement||null;
    if(!header||!header.classList.contains('border-b'))return null;
    return {header,titleBlock};
  }

  function ensureRevealButton(){
    let button=document.getElementById(BUTTON_ID);
    const visible=vm.currentUser?.role==='ADMIN'&&vm.currentPage==='client-detail'&&vm.selectedClientId!=null;
    if(!visible){
      if(button)button.remove();
      if(document.getElementById(MODAL_ID))clearReveal();
      return;
    }

    const host=findRevealHost();
    if(!host){
      if(button)button.remove();
      return;
    }

    if(!button){
      button=make('button',{
        id:BUTTON_ID,
        type:'button',
        title:'ADMIN 按需从 Vault 临时读取敏感凭证，60 秒后自动清除',
        style:'height:32px;display:inline-flex;align-items:center;justify-content:center;border:1px solid #cbd5e1;border-radius:8px;background:#fff;color:#334155;padding:0 10px;font:700 11px/1.2 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;cursor:pointer;white-space:nowrap;'
      },'安全查看客户凭证');
      button.addEventListener('click',revealSelectedClient);
    }

    host.header.style.flexWrap='wrap';
    host.header.style.gap='8px';
    host.titleBlock.style.marginRight='auto';
    if(button.parentElement!==host.header)host.header.appendChild(button);
  }
'''

count = text.count(old)
if count != 1:
    raise SystemExit(f'Unexpected floating secure credential button block count: {count}')
text = text.replace(old, new, 1)
path.write_text(text, encoding='utf-8')
print('SECURITY_REVEAL_UI_FINALIZE_OK: security=' + hashlib.sha256(path.read_bytes()).hexdigest())
