from pathlib import Path
import base64,gzip,hashlib,re,shutil
BASE_SHA='03cc1429b4423ec5bce11ce614eb29175dbe4994648d3e2f43f36945c563fadc'
CONFIRMED_SHA='51ca745531e98d1799d0ac181e97e29a1fdd6ea2eb77587b41051d9519103e43'

def sha(b): return hashlib.sha256(b).hexdigest()
parts=[Path(f'app/part-{i:03d}.txt').read_text().strip() for i in range(1,14)]
if len(parts[7])==14999: parts[7]=parts[7][:1840]+'N'+parts[7][1840:]
if len(parts[11])==14999: parts[11]=parts[11][:6048]+'r'+parts[11][6048:]
base=gzip.decompress(base64.b64decode(''.join(parts)))
if sha(base)!=BASE_SHA: raise SystemExit('base sha mismatch '+sha(base))
s=base.decode()
changes=[
('<d