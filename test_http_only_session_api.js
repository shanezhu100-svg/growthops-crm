'use strict';

const assert = require('node:assert/strict');
const handler = require('./api/crm.js');

function makeRes() {
  const headers = Object.create(null);
  return {
    statusCode: 200,
    headers,
    body: '',
    setHeader(name, value) { headers[String(name).toLowerCase()] = value; },
    end(value = '') { this.body = String(value); },
  };
}

async function invoke({ method = 'POST', headers = {}, body = {} }, fetchImpl) {
  const previousFetch = global.fetch;
  if (fetchImpl) global.fetch = fetchImpl;
  const req = { method, headers, body };
  const res = makeRes();
  try {
    await handler(req, res);
  } finally {
    global.fetch = previousFetch;
  }
  let json = null;
  try { json = res.body ? JSON.parse(res.body) : null; } catch {}
  return { res, json };
}

const sameOriginHeaders = {
  'sec-fetch-site': 'same-origin',
  origin: 'https://preview.example',
  host: 'preview.example',
  'x-forwarded-host': 'preview.example',
  'x-forwarded-proto': 'https',
};

function okJson(data) {
  return Promise.resolve({
    ok: true,
    status: 200,
    async json() { return data; },
  });
}

(async () => {
  {
    const { res, json } = await invoke({ method: 'GET' });
    assert.equal(res.statusCode, 405);
    assert.equal(res.headers.allow, 'POST');
    assert.equal(json.message, 'METHOD_NOT_ALLOWED');
  }

  {
    let called = false;
    const { res, json } = await invoke({
      headers: { ...sameOriginHeaders, 'sec-fetch-site': 'cross-site' },
      body: { rpc: 'crm_public_status', args: {} },
    }, async () => { called = true; throw new Error('must not call backend'); });
    assert.equal(res.statusCode, 403);
    assert.equal(json.message, 'CROSS_ORIGIN_REQUEST_BLOCKED');
    assert.equal(called, false);
  }

  {
    const { res, json } = await invoke({
      headers: { ...sameOriginHeaders, origin: 'https://evil.example', 'sec-fetch-site': '' },
      body: { rpc: 'crm_public_status', args: {} },
    });
    assert.equal(res.statusCode, 403);
    assert.equal(json.message, 'CROSS_ORIGIN_REQUEST_BLOCKED');
  }

  {
    const { res, json } = await invoke({
      headers: sameOriginHeaders,
      body: { rpc: 'crm_not_allowed', args: {} },
    });
    assert.equal(res.statusCode, 403);
    assert.equal(json.message, 'RPC_NOT_ALLOWED');
  }

  {
    let request = null;
    const { res, json } = await invoke({
      headers: sameOriginHeaders,
      body: {
        rpc: 'crm_login_v3',
        args: { p_username: 'admin', p_password: 'example-password', p_token: 'browser-injected' },
      },
    }, async (url, options) => {
      request = { url, options, body: JSON.parse(options.body) };
      return okJson({ token: 'server-secret-token', revision: 7, user: { id: 'u1', role: 'ADMIN' }, state: {} });
    });
    assert.equal(res.statusCode, 200);
    assert.ok(request.url.endsWith('/rest/v1/rpc/crm_login_v3'));
    assert.equal(request.body.p_username, 'admin');
    assert.equal(request.body.p_token, undefined);
    assert.equal(json.token, undefined);
    assert.equal(json.revision, 7);
    const cookie = String(res.headers['set-cookie'] || '');
    assert.match(cookie, /^__Host-growthops_crm=server-secret-token;/);
    assert.match(cookie, /Path=\//);
    assert.match(cookie, /Max-Age=604800/);
    assert.match(cookie, /HttpOnly/);
    assert.match(cookie, /Secure/);
    assert.match(cookie, /SameSite=Strict/);
    assert.equal(res.headers['cache-control'], 'no-store, max-age=0');
  }

  {
    let backendCalled = false;
    const { res, json } = await invoke({
      headers: sameOriginHeaders,
      body: { rpc: 'crm_load_state_v3', args: { p_token: 'browser-injected' } },
    }, async () => { backendCalled = true; throw new Error('must not call backend'); });
    assert.equal(res.statusCode, 401);
    assert.equal(json.message, 'SESSION_REQUIRED');
    assert.equal(backendCalled, false);
    assert.match(String(res.headers['set-cookie'] || ''), /Max-Age=0/);
  }

  {
    let requestBody = null;
    const { res, json } = await invoke({
      headers: { ...sameOriginHeaders, cookie: '__Host-growthops_crm=cookie-session-token' },
      body: { rpc: 'crm_load_state_v3', args: { p_token: 'browser-injected', p_extra: 'kept' } },
    }, async (_url, options) => {
      requestBody = JSON.parse(options.body);
      return okJson({ revision: 8, user: { id: 'u1', role: 'ADMIN' }, state: {} });
    });
    assert.equal(res.statusCode, 200);
    assert.equal(requestBody.p_token, 'cookie-session-token');
    assert.equal(requestBody.p_extra, 'kept');
    assert.equal(json.revision, 8);
  }

  {
    let requestBody = null;
    const { res } = await invoke({
      headers: { ...sameOriginHeaders, cookie: '__Host-growthops_crm=cookie-session-token' },
      body: { rpc: 'crm_logout', args: { p_token: 'browser-injected' } },
    }, async (_url, options) => {
      requestBody = JSON.parse(options.body);
      return okJson({ ok: true });
    });
    assert.equal(res.statusCode, 200);
    assert.equal(requestBody.p_token, 'cookie-session-token');
    assert.match(String(res.headers['set-cookie'] || ''), /^__Host-growthops_crm=;/);
    assert.match(String(res.headers['set-cookie'] || ''), /Max-Age=0/);
    assert.match(String(res.headers['set-cookie'] || ''), /HttpOnly/);
    assert.match(String(res.headers['set-cookie'] || ''), /Secure/);
    assert.match(String(res.headers['set-cookie'] || ''), /SameSite=Strict/);
  }

  console.log('HTTP_ONLY_SESSION_API_TESTS_OK: login-token-hidden; cookie-injection-enforced; csrf-origin-guard=active; logout-clears-cookie');
})().catch(error => {
  console.error(error);
  process.exit(1);
});
