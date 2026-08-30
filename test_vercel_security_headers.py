from pathlib import Path
import json

cfg = json.loads((Path(__file__).resolve().parent / 'vercel.json').read_text(encoding='utf-8'))
headers = {}
for rule in cfg.get('headers', []):
    if rule.get('source') == '/(.*)': headers.update({item.get('key'): item.get('value') for item in rule.get('headers', [])})
required={'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','X-Frame-Options':'DENY','X-Permitted-Cross-Domain-Policies':'none','Cross-Origin-Opener-Policy':'same-origin','Cross-Origin-Resource-Policy':'same-origin','X-Robots-Tag':'noindex, nofollow, noarchive'}
for key,value in required.items():
    if headers.get(key)!=value: raise SystemExit(f'VERCEL_SECURITY_HEADERS_TESTS_FAILED {key}')
pp=headers.get('Permissions-Policy','')
for directive in ('camera=()','microphone=()','geolocation=()','payment=()','usb=()'):
    if directive not in pp: raise SystemExit(f'VERCEL_SECURITY_HEADERS_TESTS_FAILED permissions {directive}')
csp=headers.get('Content-Security-Policy','')
for directive in ("default-src 'self'","base-uri 'self'","object-src 'none'","frame-ancestors 'none'","frame-src 'none'","form-action 'self'","connect-src 'self'","script-src 'self'","script-src-attr 'none'","style-src 'self'","style-src-elem 'self'","style-src-attr 'none'","font-src 'self' data:","img-src 'self' data: blob:","media-src 'self' data: blob:","worker-src 'none'","manifest-src 'none'",'upgrade-insecure-requests'):
    if directive not in csp: raise SystemExit(f'VERCEL_SECURITY_HEADERS_TESTS_FAILED csp {directive}')
def tokens(name): return csp.split(name+' ',1)[1].split(';',1)[0].split()
script=tokens('script-src'); script_attr=tokens('script-src-attr'); style=tokens('style-src'); style_elem=tokens('style-src-elem'); style_attr=tokens('style-src-attr'); font=tokens('font-src'); connect=tokens('connect-src'); img=tokens('img-src'); media=tokens('media-src'); worker=tokens('worker-src'); manifest=tokens('manifest-src')
all_sets=(script,script_attr,style,style_elem,style_attr,font,connect,img,media,worker,manifest)
if any('*' in x for x in all_sets): raise SystemExit('VERCEL_SECURITY_HEADERS_TESTS_FAILED CSP wildcard source')
if script != ["'self'"]: raise SystemExit('VERCEL_SECURITY_HEADERS_TESTS_FAILED script-src must be same-origin only')
for forbidden in ("'unsafe-inline'","'unsafe-eval'"):
    if forbidden in csp: raise SystemExit('VERCEL_SECURITY_HEADERS_TESTS_FAILED retired unsafe script/style capability remains: '+forbidden)
if script_attr != ["'none'"]: raise SystemExit('VERCEL_SECURITY_HEADERS_TESTS_FAILED script-src-attr must deny all HTML event handler attributes')
if style != ["'self'"] or style_elem != ["'self'"]: raise SystemExit('VERCEL_SECURITY_HEADERS_TESTS_FAILED style sources must be same-origin only')
if style_attr != ["'none'"]: raise SystemExit('VERCEL_SECURITY_HEADERS_TESTS_FAILED style-src-attr must deny all inline/dynamic style attributes')
if font != ["'self'",'data:']: raise SystemExit('VERCEL_SECURITY_HEADERS_TESTS_FAILED font-src must be same-origin/data only')
if worker != ["'none'"] or manifest != ["'none'"]: raise SystemExit('VERCEL_SECURITY_HEADERS_TESTS_FAILED unused worker/manifest capability must remain denied')
for forbidden in ('cdnjs.cloudflare.com','unpkg.com','cdn.jsdelivr.net','cdn.tailwindcss.com','fonts.googleapis.com','fonts.gstatic.com'):
    if forbidden in csp: raise SystemExit('VERCEL_SECURITY_HEADERS_TESTS_FAILED retired external dependency remains in CSP: '+forbidden)
if any(token.startswith(('https://','http://')) for group in (script,style,style_elem,font) for token in group): raise SystemExit('VERCEL_SECURITY_HEADERS_TESTS_FAILED external script/style/font source remains')
if connect != ["'self'"]: raise SystemExit('VERCEL_SECURITY_HEADERS_TESTS_FAILED connect-src must remain same-origin only')
for name,group in (('img-src',img),('media-src',media)):
    if group != ["'self'",'data:','blob:']: raise SystemExit(f'VERCEL_SECURITY_HEADERS_TESTS_FAILED {name} must remain self/data/blob only')
print('VERCEL_SECURITY_HEADERS_TESTS_OK: csp=same-origin-script+eval-free; script-attr=none; style-attr=none; unsafe-inline+unsafe-eval=absent; worker=none; manifest=none; connect=self-only; img-media=self-data-blob; coop+corp=same-origin; robots=noindex+nofollow+noarchive')
