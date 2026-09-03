import fs from 'node:fs';
import path from 'node:path';

const root=process.cwd();
const inventory=fs.readFileSync(path.join(root,'test_business_persisted_mutation_inventory.mjs'),'utf8');
const expectedBlock=/const EXPECTED = \[([\s\S]*?)\n\];/.exec(inventory)?.[1];
if(!expectedBlock)throw new Error('BUSINESS_REMAINING_MUTATION_DEBT_PROBE_FAILED: EXPECTED block missing');
const names=[...expectedBlock.matchAll(/'([A-Za-z_$][A-Za-z0-9_$]*)\[[^']+\]'/g)].map(m=>m[1]);
if(names.length!==69)throw new Error(`BUSINESS_REMAINING_MUTATION_DEBT_PROBE_FAILED: expected 69 names, got ${names.length}`);
const files=fs.readdirSync(root).filter(name=>/^test_business_.*\.mjs$/.test(name)&&!['test_business_persisted_mutation_inventory.mjs','test_business_remaining_mutation_debt_probe.mjs'].includes(name)).sort();
const text=files.map(name=>fs.readFileSync(path.join(root,name),'utf8')).join('\n');
const unmentioned=names.filter(name=>!new RegExp(`\\b${name}\\b`).test(text));
console.log(`BUSINESS_REMAINING_MUTATION_DEBT_PROBE_COUNT=${unmentioned.length}`);
for(const name of unmentioned)console.log(`BUSINESS_REMAINING_MUTATION_DEBT_PROBE_METHOD=${name}`);
throw new Error('BUSINESS_REMAINING_MUTATION_DEBT_PROBE_COMPLETE');
