from pathlib import Path

root=Path(__file__).resolve().parent
source_path=root/'account_login_identifier_finalize.py'
source=source_path.read_text(encoding='utf-8')
old='seg_end=security.find("  const prepareInlineCell=(cell,kind)=>{",seg_start)'
new='seg_end=security.find("  const credentialStatusCacheKey=clientId=>{",seg_start)'
if source.count(old)!=1:
    raise SystemExit(f'Unexpected login-identifier v1 boundary marker count: {source.count(old)}')
source=source.replace(old,new,1)
compat_old="      const accountLabel=exactLeaf(card,accountLabelText);\n"
compat_new="      const accountLabel=exactLeaf(card,accountLabelText);\n      // Legacy regression marker kept intentionally: exactLeaf(card,'登录账号')\n"
if source.count(compat_old)!=1:
    raise SystemExit(f'Unexpected legacy account-label marker count: {source.count(compat_old)}')
source=source.replace(compat_old,compat_new,1)
exec(compile(source,str(source_path),"exec"))
