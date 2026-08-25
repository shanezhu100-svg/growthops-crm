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

function assertPrivateJson(res, status) {
  assert.equal(res.statusCode, status);
  assert.equal(res.headers['cache-control'], 'no-store, max-age=0');
  assert.equal(res.headers.pragma, 'no-cache');
  assert.equal(res.headers['content-type'], 'application/json; charset=utf-8');
  assert.ok(String(res.headers['x-request-id'] || '').length >= 8);
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
  const configuredKey = process.env.GROWTHOPS_SUPABASE_SECRET_KEY;
  assert.match(String(configuredKey || ''), /^sb_secret_[A-Za-z0-9_-]+$/);

  {
    const { res, json } = await invoke({ method: 'GET' });
    assertPrivateJson(res, 405);
    assert.equal(res.headers.allow, 'POST');
    assert.equal(json.message, 'METHOD_NOT_ALLOWED');
  }

  {
    const { res, json } = await invoke({
      headers: { ...sameOriginHeaders, 'sec-fetch-site': 'cross-site' },
      body: { rpc: 'crm_public_status', args: {} },
    });
    assertPrivateJson(res, 403);
    assert.equal(json.message, 'CROSS_ORIGIN_REQUEST_BLOCKED');
  }

  {
    const { res, json } = await invoke({
      headers: sameOriginHeaders,
      body: { rpc: 'crm_not_allowed', args: {} },
    });
    assertPrivateJson(res, 403);
    assert.equal(json.message, 'RPC_NOT_ALLOWED');
  }

  {
    delete process.env.GROWTHOPS_SUPABASE_SECRET_KEY;
    try {
      const { res, json } = await invoke({
        headers: sameOriginHeaders,
        body: { rpc: 'crm_public_status', args: {} },
      });
      assertPrivateJson(res, 503);
      assert.equal(json.message, 'SERVER_IDENTITY_NOT_CONFIGURED');
    } finally {
      process.env.GROWTHOPS_SUPABASE_SECRET_KEY = configuredKey;
    }
  }

  {
    const { res, json } = await invoke({
      headers: sameOriginHeaders,
      body: { rpc: 'crm_login_v3', args: { p_username: 'admin', p_password: 'example-password' } },
    }, async () => okJson({ token: 'server-session-token', revision: 1, user: { id: 'u1', role: 'ADMIN' }, state: {} }));
    assertPrivateJson(res, 200);
    assert.equal(json.token, undefined);
    assert.match(String(res.headers['set-cookie'] || ''), /HttpOnly/);
  }

  {
    const { res, json } = await invoke({
      headers: sameOriginHeaders,
      body: { rpc: 'crm_load_state_v3', args: {} },
    });
    assertPrivateJson(res, 401);
    assert.equal(json.message, 'SESSION_REQUIRED');
  }

  {
    const { res, json } = await invoke({
      headers: { ...sameOriginHeaders, cookie: '__Host-growthops_crm=cookie-session-token' },
      body: { rpc: 'crm_load_state_v3', args: {} },
    }, async () => okJson({ revision: 2, user: { id: 'u1', role: 'ADMIN' }, state: {} }));
    assertPrivateJson(res, 200);
    assert.equal(json.revision, 2);
  }

  {
    const { res, json } = await invoke({
      headers: { ...sameOriginHeaders, cookie: '__Host-growthops_crm=cookie-session-token' },
      body: {
        rpc: 'crm_reveal_client_secret_value_v5',
        args: { p_unlock_token: 'unlock', p_client_id: 'client-1', p_platform: 'facebook', p_account_id: 'account-1', p_field: 'password' },
      },
    }, async () => errorJson(400, 'CREDENTIAL_REVEAL_THROTTLED'));
    assertPrivateJson(res, 429);
    assert.equal(json.message, 'CREDENTIAL_REVEAL_THROTTLED');
  }

  {
    const { res, json } = await invoke({
      headers: { ...sameOriginHeaders, cookie: '__Host-growthops_crm=cookie-session-token' },
      body: { rpc: 'crm_load_state_v3', args: {} },
    }, async () => errorJson(400, 'internal detail must stay hidden'));
    assertPrivateJson(res, 400);
    assert.equal(json.message, 'UPSTREAM_BAD_REQUEST');
    assert.equal(res.body.includes('internal detail'), false);
  }

  {
    const { res, json } = await invoke({
      headers: { ...sameOriginHeaders, cookie: '__Host-growthops_crm=cookie-session-token' },
      body: { rpc: 'crm_logout', args: {} },
    }, async () => okJson({ ok: true }));
    assertPrivateJson(res, 200);
    assert.equal(json.ok, true);
    assert.match(String(res.headers['set-cookie'] || ''), /Max-Age=0/);
  }

  console.log('VERCEL_CACHE_PRIVACY_TESTS_OK: method=405; origin=403; rpc=403; config=503; login=200; auth=401+200; upstream=429+400; logout=200; cache=no-store; pragma=no-cache');
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
