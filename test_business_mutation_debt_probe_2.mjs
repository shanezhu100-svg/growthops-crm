import fs from 'node:fs';
import path from 'node:path';

const root=process.cwd();
const inventory=fs.readFileSync(path.join(root,'test_business_persisted_mutation_inventory.mjs'),'utf8');
const start=inventory.indexOf('const EXPECTED = [');
const end=start<0?-1:inventory.indexOf('];',start);
if(start<0||end<0)throw new Error('BUSINESS_MUTATION_DEBT_PROBE_2_FAILED: EXPECTED inventory block missing');
const block=inventory.slice(start,end);
const names=[...block.matchAll(/'([A-Za-z_$][A-Za-z0-9_$]*)\[[^']+\]'/g)].map(m=>m[1]);
if(names.length!==69)throw new Error(`BUSINESS_MUTATION_DEBT_PROBE_2_FAILED: expected 69 inventory methods, got ${names.length}`);
const businessFiles=fs.readdirSync(root)
  .filter(name=>/^test_business_.*\.mjs$/.test(name)
    && name!=='test_business_persisted_mutation_inventory.mjs'
    && name!=='test_business_mutation_debt_probe_2.mjs')
  .sort();
const text=businessFiles.map(name=>fs.readFileSync(path.join(root,name),'utf8')).join('\n');
const unmentioned=names.filter(name=>!new RegExp(`\\b${name}\\b`).test(text));
console.log(`BUSINESS_MUTATION_DEBT_PROBE_2_LIST=${unmentioned.join(',')}`);
console.log(`BUSINESS_MUTATION_DEBT_PROBE_2_COUNT=${unmentioned.length}`);
throw new Error('BUSINESS_MUTATION_DEBT_PROBE_2_COMPLETE');
