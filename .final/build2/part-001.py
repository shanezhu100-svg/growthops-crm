from pathlib import Path
import base64,gzip,hashlib,re,shutil
BASE='03cc1429b4423ec5bce11ce614eb29175dbe4994648d3e2f43f36945c563fadc'; UI='51ca745531e98d1799d0ac181e97e29a1fdd6ea2eb77587b41051d9519103e43'
h=lambda b:hashlib.sha256(b).hexdigest()
p=[Path(f'app/part-{i:03d}.txt').read_text().strip() for i in range(1,14)]
if len(p[7])==14999:p[7]=p[7][:1840]+'N'+p[7][1840:]
if len(p[11])==14999:p[11]=p[11][:6048]+'r'+p[11][6048:]
b=gzip.decompress(base64.b64decode(''.join(p)))
if h(b)!=BASE:raise SystemExit('base sha '+h(b))
s=b.decode()
for label,color in [('当前潜客','slate'),('待跟进 / 已逾期','amber'),('高意向','cyan'),('历史成交','emerald')]:
    tone='400' if color=='slate' else '600'; old=f'text-{color}-{tone}">{label}</div></div>'; new=f'text-{color}-{