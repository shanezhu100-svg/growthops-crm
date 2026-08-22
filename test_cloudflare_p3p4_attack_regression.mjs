import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';

const TEST_SECRET = 'sb_secret_test_p3p4_attack_regression_20260822';
const SAFE_REQUEST_ID = 'p3p4-attack-0001';
process.env.GROWTHOPS_SUPABASE_SECRET_KEY = TEST_SECRET;

const require = createRequire(import.meta.url);
const vercelHandler = require('./api/crm.js');
const cfSource = readFileSync(new URL('./functions/api/crm.js', import.meta.url), 'utf8');
const cfModule = await import(`data:text/javascript;base64,${Buffer.from(cfSource).toString('base64')}`);
const cloudflareHandler = cfModule.onRequest;

function makeRes() {
  const headers = Object.create(null);
  return {
    statusCode: 200,
    headers,
    body: '',
    setHeader(name, value) { headers[String(name).toLowerCase()] = String(value); },
    end(value = '') { this.body = String(value); },
  };
}
function parseJson(text) { try { return text ? JSON.parse(text) : null; } catch { return null; } }

async function invokeVercel({ method = 'POST', headers = {}, body = {}, secret = TEST_SECRET }, fetchImpl) {
  const oldFetch = global.fetch;
  const oldSecret = process.env.GROWTHOPS_SUPABASE_SECRET_KEY;
  if (secret === null) delete process.env.GROWTHOPS_SUPABASE_SECRET_KEY;
  else process.env.GROWTHOPS_SUPABASE_SECRET_KEY = secret;
  if (fetchImpl) global.fetch = fetchImpl;
  const res = makeRes();
  try {
    await vercelHandler({ method, headers, body }, res);
  } finally {
    global.fetch = oldFetch;
    if (oldSecret === undefined) delete process.env.GROWTHOPS_SUPABASE_SECRET_KEY;
    else process.env.GROWTHOPS_SUPABASE_SECRET_KEY = oldSecret;
  }
  return { status: res.statusCode, headers: res.headers, json: parseJson(res.body) };
}

async function invokeCf({ method = 'POST', headers = {}, body = {}, rawBody = null, secret = TEST_SECRET }, fetchImpl) {
  const oldFetch = global.fetch;
  if (fetchImpl) global.fetch = fetchImpl;
  const init = { method, headers };
  if (method !== 'GET' && method !== 'HEAD') init.body = rawBody !== null ? rawBody : JSON.stringify(body);
  const request = new Request('https://preview.example/api/crm', init);
  let response;
  try {
    response = await cloudflareHandler({ request, env: secret === null ? {} : { GROWTHOPS_SUPABASE_SECRET_KEY: secret } });
  } finally {
    global.fetch = oldFetch;
  }
  const text = await response.text();
  return {
    status: response.status,
    headers: {
      allow: response.headers.get('allow'),
      'set-cookie': response.headers.get('set-cookie'),
      'x-request-id': response.headers.get('x-request-id'),
    },
    json: parseJson(text),
  };
}

function okJson(data) {
  return Promise.resolve(new Response(JSON.stringify(data), { status: 200, headers: { 'Content-Type': 'application/json' } }));
}
function errJson(status, data) {
  return Promise.resolve(new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } }));
}

const sameOrigin = {
  'sec-fetch-site': 'same-origin',
  origin: 'https://preview.example',
  host: 'preview.example',
  'x-forwarded-host': 'preview.example',
  'x-forwarded-proto': 'https',
  'x-request-id': SAFE_REQUEST_ID,
};
const sessionHeaders = { ...sameOrigin, cookie: '__Host-growthops_crm=trusted-cookie-session' };
const invokers = [invokeVercel, invokeCf];

// Cross-origin attacker cannot use an otherwise valid HttpOnly session cookie.
for (const invoke of invokers) {
  let calls = 0;
  const result = await invoke({
    headers: { ...sessionHeaders, origin: 'https://attacker.example', 'sec-fetch-site': 'cross-site' },
    body: { rpc: 'crm_reveal_client_secret_value_v5', args: { p_unlock_token: 'forged-unlock', p_client_id: 'victim', p_platform: 'facebook', p_account_id: 'a1', p_field: 'password' } },
  }, async () => { calls++; return okJson({ value: 'should-never-run' }); });
  assert.equal(result.status, 403);
  assert.deepEqual(result.json, { message: 'CROSS_ORIGIN_REQUEST_BLOCKED' });
  assert.equal(calls, 0);
}

// Historical broad reveal and internal Vault RPC names stay unreachable at the BFF.
const blockedRpcs = [
  'crm_reveal_client_secret_field_v3',
  'crm_reveal_client_secret_field_v4',
  'crm_reveal_client_secrets',
  'crm_read_workspace_secrets',
  'crm_write_workspace_secrets',
];
for (const rpc of blockedRpcs) {
  for (const invoke of invokers) {
    let calls = 0;
    const result = await invoke({ headers: sessionHeaders, body: { rpc, args: { p_token: 'forged' } } }, async () => { calls++; return okJson({}); });
    assert.equal(result.status, 403, rpc);
    assert.deepEqual(result.json, { message: 'RPC_NOT_ALLOWED' });
    assert.equal(calls, 0);
  }
}

// Forging p_token is useless without the HttpOnly cookie, even for privileged allowlisted RPCs.
const authAttackRpcs = [
  'crm_unlock_credentials_v1',
  'crm_reveal_client_secret_value_v5',
  'crm_list_users',
  'crm_upsert_user',
  'crm_delete_user',
  'crm_client_account_safe_summary',
  'crm_save_state',
];
for (const rpc of authAttackRpcs) {
  for (const invoke of invokers) {
    let calls = 0;
    const result = await invoke({
      headers: sameOrigin,
      body: { rpc, args: { p_token: 'attacker-forged-token', p_role: 'ADMIN', role: 'ADMIN', p_workspace_id: 'other-workspace' } },
    }, async () => { calls++; return okJson({}); });
    assert.equal(result.status, 401, rpc);
    assert.deepEqual(result.json, { message: 'SESSION_REQUIRED' });
    assert.match(String(result.headers['set-cookie'] || ''), /Max-Age=0/);
    assert.equal(calls, 0);
  }
}

// With a real cookie, attacker-controlled p_token is always replaced by the cookie session token.
for (const rpc of ['crm_unlock_credentials_v1', 'crm_reveal_client_secret_value_v5', 'crm_upsert_user', 'crm_delete_user']) {
  for (const invoke of invokers) {
    let upstreamBody = null;
    const result = await invoke({
      headers: sessionHeaders,
      body: { rpc, args: { p_token: 'attacker-forged-token', p_role: 'ADMIN', role: 'ADMIN' } },
    }, async (_url, options) => {
      upstreamBody = JSON.parse(options.body);
      return okJson(rpc === 'crm_reveal_client_secret_value_v5' ? { value: 'synthetic-single-value' } : {});
    });
    assert.equal(result.status, 200, rpc);
    assert.equal(upstreamBody.p_token, 'trusted-cookie-session');
    assert.notEqual(upstreamBody.p_token, 'attacker-forged-token');
  }
}

// Invalid/oversized request IDs are never reflected; safe IDs still round-trip.
for (const maliciousId of ['attack<script>', 'x'.repeat(129)]) {
  for (const invoke of invokers) {
    const result = await invoke({ headers: { ...sameOrigin, 'x-request-id': maliciousId }, body: { rpc: 'crm_public_status', args: {} } }, () => okJson({ initialized: true }));
    const returned = String(result.headers['x-request-id'] || '');
    assert.notEqual(returned, maliciousId);
    assert.match(returned, /^[A-Za-z0-9._:-]{8,128}$/);
  }
}
for (const invoke of invokers) {
  const result = await invoke({ headers: sameOrigin, body: { rpc: 'crm_public_status', args: {} } }, () => okJson({ initialized: true }));
  assert.equal(result.headers['x-request-id'], SAFE_REQUEST_ID);
}

// Malformed JSON is rejected before any backend call.
{
  let calls = 0;
  const v = await invokeVercel({ headers: sameOrigin, body: '{' }, async () => { calls++; return okJson({}); });
  const c = await invokeCf({ headers: sameOrigin, rawBody: '{' }, async () => { calls++; return okJson({}); });
  assert.equal(v.status, 400);
  assert.equal(c.status, 400);
  assert.deepEqual(v.json, { message: 'INVALID_JSON' });
  assert.deepEqual(c.json, { message: 'INVALID_JSON' });
  assert.equal(calls, 0);
}

// Array/non-object args cannot smuggle a browser token; the server injects only the cookie token.
for (const invoke of invokers) {
  let upstreamBody = null;
  const result = await invoke({ headers: sessionHeaders, body: { rpc: 'crm_load_state_v3', args: ['p_token', 'attacker-forged-token'] } }, async (_url, options) => {
    upstreamBody = JSON.parse(options.body);
    return okJson({ revision: 1, state: {} });
  });
  assert.equal(result.status, 200);
  assert.deepEqual(upstreamBody, { p_token: 'trusted-cookie-session' });
}

// Login failures and missing-session responses cannot leak a token or create a cookie.
for (const invoke of invokers) {
  const failed = await invoke({ headers: sameOrigin, body: { rpc: 'crm_login_v3', args: { p_username: 'x', p_password: 'wrong', p_token: 'forged' } } }, () => okJson({ error: 'INVALID_CREDENTIALS', token: 'must-not-leak' }));
  assert.equal(failed.status, 401);
  assert.deepEqual(failed.json, { message: 'LOGIN_FAILED' });
  assert.equal(failed.json.token, undefined);
  assert.equal(failed.headers['set-cookie'] || null, null);

  const missing = await invoke({ headers: sameOrigin, body: { rpc: 'crm_login_v3', args: { p_username: 'x', p_password: 'y' } } }, () => okJson({ user: { role: 'ADMIN' }, state: {} }));
  assert.equal(missing.status, 502);
  assert.deepEqual(missing.json, { message: 'LOGIN_SESSION_MISSING' });
  assert.equal(missing.headers['set-cookie'] || null, null);
}

// Upstream raw errors never reach the browser/logs, and session-related failures clear the cookie.
for (const invoke of invokers) {
  const logs = [];
  const oldError = console.error;
  console.error = (...args) => logs.push(args.join(' '));
  try {
    const result = await invoke({
      headers: sessionHeaders,
      body: { rpc: 'crm_save_state', args: { p_token: 'forged', p_state: { password: 'ATTACK_PASSWORD', twofa: 'ATTACK_2FA' } } },
    }, () => errJson(500, { message: `raw backend leak ATTACK_PASSWORD ATTACK_2FA ${TEST_SECRET}` }));
    assert.equal(result.status, 502);
    assert.deepEqual(result.json, { message: 'UPSTREAM_REQUEST_FAILED' });
    const joined = logs.join('\n');
    assert.equal(joined.includes('ATTACK_PASSWORD'), false);
    assert.equal(joined.includes('ATTACK_2FA'), false);
    assert.equal(joined.includes(TEST_SECRET), false);
    assert.ok(joined.includes('crm_save_state'));
    assert.ok(joined.includes(SAFE_REQUEST_ID));
  } finally {
    console.error = oldError;
  }

  const invalidSession = await invoke({ headers: sessionHeaders, body: { rpc: 'crm_load_state_v3', args: {} } }, () => errJson(401, { message: 'TOKEN internal detail must not leak' }));
  assert.equal(invalidSession.status, 401);
  assert.deepEqual(invalidSession.json, { message: 'SESSION_INVALID' });
  assert.match(String(invalidSession.headers['set-cookie'] || ''), /Max-Age=0/);
}

// Logout clears the browser cookie even when the upstream logout call fails.
for (const invoke of invokers) {
  const result = await invoke({ headers: sessionHeaders, body: { rpc: 'crm_logout', args: { p_token: 'forged' } } }, () => errJson(500, { message: 'internal logout failure' }));
  assert.equal(result.status, 502);
  assert.deepEqual(result.json, { message: 'UPSTREAM_REQUEST_FAILED' });
  assert.match(String(result.headers['set-cookie'] || ''), /Max-Age=0/);
}

console.log('CLOUDFLARE_P3P4_ATTACK_REGRESSION_OK: cross-origin=blocked; forged-token=blocked; broad-reveal=blocked; request-id-injection=filtered; upstream-errors=sanitized; logout-failure=clears-cookie');
