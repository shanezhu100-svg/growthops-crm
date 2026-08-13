tone}">{label}</div><i class="fa-solid fa-arrow-pointer text-[9px] text-{color}-300"></i></div>'
    if old not in s:raise SystemExit('ui anchor '+label)
    s=s.replace(old,new,1)
old="actualProfitConfirmed?'已确认':'当前'";new="actualProfitConfirmed?'已确认':'待返点确认'"
if old not in s:raise SystemExit('profit label anchor')
s=s.replace(old,new,1)
if h(s.encode())!=UI:raise SystemExit('ui sha '+h(s.encode()))
c=Path('index.html').read_text();u=re.search(r"SUPABASE_URL\s*=\s*['\"]([^'\"]+)",c);k=re.search(r"(?:API_KEY|SUPABASE_KEY)\s*=\s*['\"]([^'\"]+)",c)
if not u or not k:raise SystemExit('public cloud config missing')
s=s.replace('\ncreateApp({','\nwindow.__CRM_APP__=createApp({',1).replace('</body>','<script src="/cloud-adapter.js"></script>\n</b