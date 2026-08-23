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

function errorJson(status, message, hint = '') {
  return Promise.resolve({
    ok: false,
    status,
    async json() { return { message, hint }; },
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

  // Broader credential bundle RPCs must never be proxy-allowlisted.
  for (const rpc of ['crm_reveal_client_secret_field_v4','crm_reveal_client_secret_field_v3','crm_reveal_client_secrets']) {
    let called = false;
    const { res, json } = await invoke({
      headers: { ...sameOriginHeaders, cookie: '__Host-growthops_crm=cookie-session-token' },
      body: { rpc, args: {} },
    }, async () => { called = true; return okJson({}); });
    assert.equal(res.statusCode, 403);
    assert.equal(json.message, 'RPC_NOT_ALLOWED');
    assert.equal(called, false);
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

  // v5 is allowed, cookie token wins over a forged browser p_token, and the scalar
  // response is passed through without adding any broader secret bundle.
  {
    let requestUrl = '';
    let requestBody = null;
    const { res, json } = await invoke({
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
    }, async (url, options) => {
      requestUrl = url;
      requestBody = JSON.parse(options.body);
      return okJson({ value: 'one-secret-value' });
    });
    assert.equal(res.statusCode, 200);
    assert.ok(requestUrl.endsWith('/rest/v1/rpc/crm_reveal_client_secret_value_v5'));
    assert.equal(requestBody.p_token, 'cookie-session-token');
    assert.equal(requestBody.p_field, 'password');
    assert.deepEqual(json, { value: 'one-secret-value' });
    assert.equal(Object.prototype.hasOwnProperty.call(json, 'accountSecrets'), false);
  }

  // Known credential-control errors are safe UI codes and may cross the BFF so the
  // browser can distinguish rate limiting from a generic backend failure.
  {
    const { res, json } = await invoke({
      headers: { ...sameOriginHeaders, cookie: '__Host-growthops_crm=cookie-session-token' },
      body: {
        rpc: 'crm_reveal_client_secret_value_v5',
        args: { p_unlock_token: 'unlock-example', p_client_id: 'client-1', p_platform: 'facebook', p_account_id: 'account-1', p_field: 'password' },
      },
    }, async () => errorJson(400, 'CREDENTIAL_REVEAL_THROTTLED'));
    assert.equal(res.statusCode, 429);
    assert.equal(json.message, 'CREDENTIAL_REVEAL_THROTTLED');
    assert.equal(res.headers['set-cookie'], undefined);
  }

  // Arbitrary upstream text must remain hidden even when PostgREST returns 400.
  {
    const { res, json } = await invoke({
      headers: { ...sameOriginHeaders, cookie: '__Host-growthops_crm=cookie-session-token' },
      body: {
        rpc: 'crm_reveal_client_secret_value_v5',
        args: { p_unlock_token: 'unlock-example', p_client_id: 'client-1', p_platform: 'facebook', p_account_id: 'account-1', p_field: 'password' },
      },
    }, async () => errorJson(400, 'internal table name and sensitive detail'));
    assert.equal(res.statusCode, 400);
    assert.equal(json.message, 'UPSTREAM_BAD_REQUEST');
    assert.equal(res.body.includes('internal table name'), false);
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

  console.log('HTTP_ONLY_SESSION_API_TESTS_OK: login-token-hidden; cookie-injection-enforced; csrf-origin-guard=active; credential-reveal=v5-only; safe-credential-errors=allowlisted; unknown-errors=sanitized; logout-clears-cookie');
})().catch(error => {
  console.error(error);
  process.exit(1);
});
