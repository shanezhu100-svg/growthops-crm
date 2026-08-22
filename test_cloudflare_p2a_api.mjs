import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const vercelHandler = require('./api/crm.js');
const cloudflareSource = readFileSync(new URL('./functions/api/crm.js', import.meta.url), 'utf8');
const cloudflareModule = await import(`data:text/javascript;base64,${Buffer.from(cloudflareSource).toString('base64')}`);
const cloudflareHandler = cloudflareModule.onRequest;

function makeVercelRes() {
  const headers = Object.create(null);
  return {
    statusCode: 200,
    headers,
    body: '',
    setHeader(name, value) { headers[String(name).toLowerCase()] = String(value); },
    end(value = '') { this.body = String(value); },
  };
}

function parseJson(text) {
  try { return text ? JSON.parse(text) : null; } catch { return null; }
}

async function invokeVercel({ method = 'POST', headers = {}, body = {} }, fetchImpl) {
  const previousFetch = global.fetch;
  if (fetchImpl) global.fetch = fetchImpl;
  const req = { method, headers, body };
  const res = makeVercelRes();
  try {
    await vercelHandler(req, res);
  } finally {
    global.fetch = previousFetch;
  }
  return {
    status: res.statusCode,
    headers: res.headers,
    json: parseJson(res.body),
  };
}

async function invokeCloudflare({ method = 'POST', headers = {}, body = {}, rawBody = null }, fetchImpl) {
  const previousFetch = global.fetch;
  if (fetchImpl) global.fetch = fetchImpl;
  const init = { method, headers };
  if (method !== 'GET' && method !== 'HEAD') {
    init.body = rawBody !== null ? rawBody : (typeof body === 'string' ? body : JSON.stringify(body));
  }
  const request = new Request('https://preview.example/api/crm', init);
  let response;
  try {
    response = await cloudflareHandler({ request, env: {} });
  } finally {
    global.fetch = previousFetch;
  }
  const text = await response.text();
  return {
    status: response.status,
    headers: {
      allow: response.headers.get('allow'),
      'cache-control': response.headers.get('cache-control'),
      pragma: response.headers.get('pragma'),
      'set-cookie': response.headers.get('set-cookie'),
    },
    json: parseJson(text),
  };
}

const sameOriginHeaders = {
  'sec-fetch-site': 'same-origin',
  origin: 'https://preview.example',
  host: 'preview.example',
  'x-forwarded-host': 'preview.example',
  'x-forwarded-proto': 'https',
};

function okJson(data) {
  return Promise.resolve(new Response(JSON.stringify(data), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  }));
}

function errorJson(status, data) {
  return Promise.resolve(new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  }));
}

function header(result, name) {
  return result.headers[String(name).toLowerCase()] ?? null;
}

async function assertBasicParity(input, fetchImpl) {
  const [vercel, cloudflare] = await Promise.all([
    invokeVercel(input, fetchImpl),
    invokeCloudflare(input, fetchImpl),
  ]);
  assert.equal(cloudflare.status, vercel.status);
  assert.deepEqual(cloudflare.json, vercel.json);
  assert.equal(header(cloudflare, 'allow'), header(vercel, 'allow'));
  assert.equal(header(cloudflare, 'cache-control'), header(vercel, 'cache-control'));
  assert.equal(header(cloudflare, 'pragma'), header(vercel, 'pragma'));
  assert.equal(header(cloudflare, 'set-cookie'), header(vercel, 'set-cookie'));
  return { vercel, cloudflare };
}

// Static source guard: P2-A must not broaden the secret surface or introduce a privileged key.
for (const required of [
  "const COOKIE_NAME = '__Host-growthops_crm';",
  "'crm_public_status'",
  "'crm_login_v3'",
  "'crm_load_state_v3'",
  "'crm_save_state'",
  "'crm_logout'",
  "'crm_list_users'",
  "'crm_upsert_user'",
  "'crm_delete_user'",
  "'crm_client_account_safe_summary'",
  "'crm_unlock_credentials_v1'",
  "'crm_reveal_client_secret_value_v5'",
  'HttpOnly; Secure; SameSite=Strict',
]) {
  assert.ok(cloudflareSource.includes(required), `missing Cloudflare P2-A marker: ${required}`);
}
for (const forbidden of [
  "'crm_reveal_client_secret_field_v4'",
  "'crm_reveal_client_secret_field_v3'",
  "'crm_reveal_client_secrets'",
  'SUPABASE_SERVICE_ROLE_KEY',
  'service_role',
]) {
  assert.equal(cloudflareSource.includes(forbidden), false, `forbidden Cloudflare P2-A marker: ${forbidden}`);
}

// Method gate.
await assertBasicParity({ method: 'GET' });

// Cross-origin and Origin mismatch gates must run before backend access.
for (const headers of [
  { ...sameOriginHeaders, 'sec-fetch-site': 'cross-site' },
  { ...sameOriginHeaders, origin: 'https://evil.example', 'sec-fetch-site': '' },
]) {
  let calls = 0;
  const fetchImpl = async () => { calls += 1; throw new Error('backend must not be called'); };
  const vercel = await invokeVercel({ headers, body: { rpc: 'crm_public_status', args: {} } }, fetchImpl);
  const cloudflare = await invokeCloudflare({ headers, body: { rpc: 'crm_public_status', args: {} } }, fetchImpl);
  assert.equal(vercel.status, 403);
  assert.equal(cloudflare.status, 403);
  assert.equal(vercel.json.message, 'CROSS_ORIGIN_REQUEST_BLOCKED');
  assert.equal(cloudflare.json.message, 'CROSS_ORIGIN_REQUEST_BLOCKED');
  assert.equal(calls, 0);
}

// Invalid JSON.
{
  const vercel = await invokeVercel({ headers: sameOriginHeaders, body: '{' });
  const cloudflare = await invokeCloudflare({ headers: sameOriginHeaders, rawBody: '{' });
  assert.equal(vercel.status, 400);
  assert.equal(cloudflare.status, 400);
  assert.deepEqual(cloudflare.json, vercel.json);
}

// Non-allowlisted and broad credential bundle RPCs must remain blocked.
for (const rpc of [
  'crm_not_allowed',
  'crm_reveal_client_secret_field_v4',
  'crm_reveal_client_secret_field_v3',
  'crm_reveal_client_secrets',
]) {
  let calls = 0;
  const fetchImpl = async () => { calls += 1; return okJson({}); };
  const input = {
    headers: { ...sameOriginHeaders, cookie: '__Host-growthops_crm=cookie-session-token' },
    body: { rpc, args: {} },
  };
  const vercel = await invokeVercel(input, fetchImpl);
  const cloudflare = await invokeCloudflare(input, fetchImpl);
  assert.equal(vercel.status, 403);
  assert.equal(cloudflare.status, 403);
  assert.equal(vercel.json.message, 'RPC_NOT_ALLOWED');
  assert.equal(cloudflare.json.message, 'RPC_NOT_ALLOWED');
  assert.equal(calls, 0);
}

// Login: browser p_token stripped, server token hidden from JSON, exact HttpOnly cookie parity.
{
  const input = {
    headers: sameOriginHeaders,
    body: {
      rpc: 'crm_login_v3',
      args: { p_username: 'admin', p_password: 'example-password', p_token: 'browser-injected' },
    },
  };
  const makeFetch = capture => async (url, options) => {
    capture.url = String(url);
    capture.body = JSON.parse(options.body);
    return okJson({ token: 'server-secret-token', revision: 7, user: { id: 'u1', role: 'ADMIN' }, state: {} });
  };
  const vCapture = {};
  const cCapture = {};
  const vercel = await invokeVercel(input, makeFetch(vCapture));
  const cloudflare = await invokeCloudflare(input, makeFetch(cCapture));
  assert.equal(vercel.status, 200);
  assert.equal(cloudflare.status, 200);
  assert.deepEqual(cloudflare.json, vercel.json);
  assert.equal(cloudflare.json.token, undefined);
  assert.deepEqual(cCapture.body, vCapture.body);
  assert.equal(cCapture.body.p_token, undefined);
  assert.equal(cCapture.url, vCapture.url);
  assert.equal(header(cloudflare, 'set-cookie'), header(vercel, 'set-cookie'));
  assert.match(header(cloudflare, 'set-cookie'), /^__Host-growthops_crm=server-secret-token;/);
  assert.match(header(cloudflare, 'set-cookie'), /Max-Age=604800/);
  assert.match(header(cloudflare, 'set-cookie'), /HttpOnly/);
  assert.match(header(cloudflare, 'set-cookie'), /Secure/);
  assert.match(header(cloudflare, 'set-cookie'), /SameSite=Strict/);
}

// Missing auth cookie must not call Supabase and must clear stale cookie state.
{
  const input = { headers: sameOriginHeaders, body: { rpc: 'crm_load_state_v3', args: { p_token: 'browser-injected' } } };
  let vCalls = 0;
  let cCalls = 0;
  const vercel = await invokeVercel(input, async () => { vCalls += 1; throw new Error('backend must not be called'); });
  const cloudflare = await invokeCloudflare(input, async () => { cCalls += 1; throw new Error('backend must not be called'); });
  assert.equal(vercel.status, 401);
  assert.equal(cloudflare.status, 401);
  assert.deepEqual(cloudflare.json, vercel.json);
  assert.equal(vCalls, 0);
  assert.equal(cCalls, 0);
  assert.match(header(cloudflare, 'set-cookie'), /Max-Age=0/);
}

// Authenticated load: Cookie token must replace forged browser p_token.
{
  const input = {
    headers: { ...sameOriginHeaders, cookie: '__Host-growthops_crm=cookie-session-token' },
    body: { rpc: 'crm_load_state_v3', args: { p_token: 'browser-injected', p_extra: 'kept' } },
  };
  const makeFetch = capture => async (_url, options) => {
    capture.body = JSON.parse(options.body);
    return okJson({ revision: 8, user: { id: 'u1', role: 'ADMIN' }, state: {} });
  };
  const vCapture = {};
  const cCapture = {};
  const vercel = await invokeVercel(input, makeFetch(vCapture));
  const cloudflare = await invokeCloudflare(input, makeFetch(cCapture));
  assert.equal(vercel.status, 200);
  assert.equal(cloudflare.status, 200);
  assert.deepEqual(cloudflare.json, vercel.json);
  assert.deepEqual(cCapture.body, vCapture.body);
  assert.equal(cCapture.body.p_token, 'cookie-session-token');
  assert.equal(cCapture.body.p_extra, 'kept');
}

// v5 single-value reveal only.
{
  const input = {
    headers: { ...sameOriginHeaders, cookie: '__Host-growthops_crm=cookie-session-token' },
    body: {
      rpc: 'crm_reveal_client_secret_value_v5',
      args: {
        p_token: 'browser-injected',
        p_unlock_token: 'unlock-example',
        p_client_id: 'client-1',
        p_platform: 'facebook',
        p_account_id: 'account-1',
        p_field: 'password',
      },
    },
  };
  const makeFetch = capture => async (url, options) => {
    capture.url = String(url);
    capture.body = JSON.parse(options.body);
    return okJson({ value: 'one-secret-value' });
  };
  const vCapture = {};
  const cCapture = {};
  const vercel = await invokeVercel(input, makeFetch(vCapture));
  const cloudflare = await invokeCloudflare(input, makeFetch(cCapture));
  assert.equal(vercel.status, 200);
  assert.equal(cloudflare.status, 200);
  assert.deepEqual(cloudflare.json, { value: 'one-secret-value' });
  assert.deepEqual(cloudflare.json, vercel.json);
  assert.equal(cCapture.body.p_token, 'cookie-session-token');
  assert.equal(cCapture.body.p_field, 'password');
  assert.equal(cCapture.url, vCapture.url);
  assert.equal(Object.prototype.hasOwnProperty.call(cloudflare.json, 'accountSecrets'), false);
}

// Logout success clears cookie; logout backend failure also clears it.
for (const backend of [
  () => okJson({ ok: true }),
  () => errorJson(500, { message: 'logout backend failed' }),
]) {
  const input = {
    headers: { ...sameOriginHeaders, cookie: '__Host-growthops_crm=cookie-session-token' },
    body: { rpc: 'crm_logout', args: { p_token: 'browser-injected' } },
  };
  const vercel = await invokeVercel(input, backend);
  const cloudflare = await invokeCloudflare(input, backend);
  assert.equal(cloudflare.status, vercel.status);
  assert.deepEqual(cloudflare.json, vercel.json);
  assert.equal(header(cloudflare, 'set-cookie'), header(vercel, 'set-cookie'));
  assert.match(header(cloudflare, 'set-cookie'), /^__Host-growthops_crm=;/);
  assert.match(header(cloudflare, 'set-cookie'), /Max-Age=0/);
}

console.log('CLOUDFLARE_P2A_API_PARITY_TESTS_OK: method=post-only; csrf=same-origin; allowlist=exact; login-token-hidden; cookie-injection=exact; credential-reveal=v5-only; logout-clears-cookie');
