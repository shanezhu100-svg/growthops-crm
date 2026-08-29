import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const config = JSON.parse(readFileSync(new URL('./vercel.json', import.meta.url), 'utf8'));
const rules = (config.headers || []).filter((rule) => rule.source === '/(.*)');
assert.equal(rules.length, 1, 'expected one Vercel catch-all header rule');
const expectedHeaders = Object.fromEntries(
  rules[0].headers.map(({ key, value }) => [String(key).toLowerCase(), String(value)]),
);
assert.equal(Object.keys(expectedHeaders).length, 9, 'expected nine browser hardening headers');
assert.equal(expectedHeaders['x-robots-tag'], 'noindex, nofollow, noarchive');
assert.equal(expectedHeaders['cross-origin-resource-policy'], 'same-origin');

const cfSource = readFileSync(new URL('./functions/api/crm.js', import.meta.url), 'utf8');
const cfModule = await import(`data:text/javascript;base64,${Buffer.from(cfSource).toString('base64')}`);
const handler = cfModule.onRequest;

async function invoke(request) {
  return handler({ request, env: {} });
}

const cases = [
  new Request('https://preview.example/api/crm', {
    method: 'GET',
    headers: { 'x-request-id': 'function-header-get-0001' },
  }),
  new Request('https://preview.example/api/crm', {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'sec-fetch-site': 'cross-site',
      origin: 'https://attacker.example',
      'x-request-id': 'function-header-origin-0001',
    },
    body: JSON.stringify({ rpc: 'crm_public_status', args: {} }),
  }),
  new Request('https://preview.example/api/crm', {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'sec-fetch-site': 'same-origin',
      origin: 'https://preview.example',
      'x-request-id': 'function-header-config-0001',
    },
    body: JSON.stringify({ rpc: 'crm_public_status', args: {} }),
  }),
];

const expectedStatuses = [405, 403, 503];
for (let i = 0; i < cases.length; i += 1) {
  const response = await invoke(cases[i]);
  assert.equal(response.status, expectedStatuses[i]);
  for (const [key, value] of Object.entries(expectedHeaders)) {
    assert.equal(response.headers.get(key), value, `Cloudflare Function header mismatch: ${key}`);
  }
  assert.equal(response.headers.get('cache-control'), 'no-store, max-age=0');
  assert.equal(response.headers.get('pragma'), 'no-cache');
  assert.match(String(response.headers.get('x-request-id') || ''), /^function-header-/);
}

assert.equal((await invoke(cases[0])).headers.get('allow'), 'POST');
console.log('CLOUDFLARE_FUNCTION_SECURITY_HEADERS_TESTS_OK: source=vercel.json; responses=method+origin+config-failure; headers=9; corp=same-origin; robots=noindex+nofollow+noarchive; cache=no-store; parity=exact');
