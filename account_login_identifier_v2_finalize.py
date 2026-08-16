from pathlib import Path

root=Path(__file__).resolve().parent
source_path=root/'account_login_identifier_finalize.py'
source=source_path.read_text(encoding='utf-8')
old='seg_end=security.find("  const prepareInlineCell=(cell,kind)=>{",seg_start)'
new='seg_end=security.find("  const credentialStatusCacheKey=clientId=>{",seg_start)'
if source.count(old)!=1:
    raise SystemExit(f'Unexpected login-identifier v1 boundary marker count: {source.count(old)}')
source=source.replace(old,new,1)
exec(compile(source,str(source_path),"exec"))
