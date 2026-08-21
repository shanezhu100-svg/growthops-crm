'use strict';

const SUPABASE_URL = process.env.GROWTHOPS_SUPABASE_URL || 'https://avahcwyxparbcjdfglzx.supabase.co';
const SUPABASE_KEY = process.env.GROWTHOPS_SUPABASE_PUBLISHABLE_KEY || 'sb_publishable_5Wkk8Bb1zh5lB1YEnvJBPg_Uvmtv62w';
const COOKIE_NAME = '__Host-growthops_crm';
const COOKIE_MAX_AGE = 7 * 24 * 60 * 60;

const PUBLIC_RPCS = new Set([
  'crm_public_status',
]);

const LOGIN_RPCS = new Set([
  'crm_login_v3',
]);

const AUTH_RPCS = new Set([
  'crm_load_state_v3',
  'crm_save_state',
  'crm_logout',
  'crm_list_users',
  'crm_upsert_user',
  'crm_delete_user',
  'crm_client_account_safe_summary',
  'crm_unlock_credentials_v1',
  'crm_reveal_client_secret_field_v4',
]);

const ALL_RPCS = new Set([...PUBLIC_RPCS, ...LOGIN_RPCS, ...AUTH_RPCS]);

function parseCookies(header = '') {
  const out = {};
  for (const part of String(header).split(';')) {
    const i = part.indexOf('=');
    if (i <= 0) continue;
    const key = part.slice(0, i).trim();
    const raw = part.slice(i + 1).trim();
    try { out[key] = decodeURIComponent(raw); } catch { out[key] = raw; }
  }
  return out;
}

function sessionCookie(token) {
  return `${COOKIE_NAME}=${encodeURIComponent(token)}; Path=/; Max-Age=${COOKIE_MAX_AGE}; HttpOnly; Secure; SameSite=Strict`;
}

function clearSessionCookie() {
  return `${COOKIE_NAME}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Strict`;
}

function sameOrigin(req) {
  const site = String(req.headers['sec-fetch-site'] || '').toLowerCase();
  if (site && site !== 'same-origin' && site !== 'none') return false;

  const origin = String(req.headers.origin || '');
  if (!origin) return true;
  const host = String(req.headers['x-forwarded-host'] || req.headers.host || '');
  const proto = String(req.headers['x-forwarded-proto'] || 'https').split(',')[0].trim();
  if (!host) return false;
  return origin === `${proto}://${host}`;
}

function json(res, status, body) {
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Cache-Control', 'no-store, max-age=0');
  res.setHeader('Pragma', 'no-cache');
  res.end(JSON.stringify(body));
}

function bodyObject(req) {
  if (req.body && typeof req.body === 'object') return req.body;
  if (typeof req.body === 'string' && req.body) {
    try { return JSON.parse(req.body); } catch { return null; }
  }
  return {};
}

async function supabaseRpc(name, args) {
  const response = await fetch(`${SUPABASE_URL}/rest/v1/rpc/${encodeURIComponent(name)}`, {
    method: 'POST',
    headers: {
      apikey: SUPABASE_KEY,
      'Content-Type': 'application/json',
      'Cache-Control': 'no-store',
    },
    body: JSON.stringify(args || {}),
  });

  let data = null;
  try { data = await response.json(); } catch {}
  if (!response.ok) {
    const message = data?.message || data?.hint || `请求失败 ${response.status}`;
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return data;
}

function stripSessionToken(data) {
  if (!data || typeof data !== 'object' || Array.isArray(data)) return data;
  if (!Object.prototype.hasOwnProperty.call(data, 'token')) return data;
  const safe = { ...data };
  delete safe.token;
  return safe;
}

module.exports = async function handler(req, res) {
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST');
    return json(res, 405, { message: 'METHOD_NOT_ALLOWED' });
  }
  if (!sameOrigin(req)) return json(res, 403, { message: 'CROSS_ORIGIN_REQUEST_BLOCKED' });

  const body = bodyObject(req);
  if (!body) return json(res, 400, { message: 'INVALID_JSON' });

  const rpc = String(body.rpc || '');
  const args = body.args && typeof body.args === 'object' && !Array.isArray(body.args) ? { ...body.args } : {};
  if (!ALL_RPCS.has(rpc)) return json(res, 403, { message: 'RPC_NOT_ALLOWED' });

  const cookies = parseCookies(req.headers.cookie || '');
  const sessionToken = String(cookies[COOKIE_NAME] || '');

  try {
    if (LOGIN_RPCS.has(rpc)) {
      delete args.p_token;
      const data = await supabaseRpc(rpc, args);
      if (data?.error) return json(res, 401, { message: String(data.error) });
      const token = String(data?.token || '');
      if (!token) return json(res, 502, { message: 'LOGIN_SESSION_MISSING' });
      res.setHeader('Set-Cookie', sessionCookie(token));
      return json(res, 200, stripSessionToken(data));
    }

    if (PUBLIC_RPCS.has(rpc)) {
      delete args.p_token;
      return json(res, 200, stripSessionToken(await supabaseRpc(rpc, args)));
    }

    if (!sessionToken) {
      res.setHeader('Set-Cookie', clearSessionCookie());
      return json(res, 401, { message: 'SESSION_REQUIRED' });
    }

    args.p_token = sessionToken;

    if (rpc === 'crm_logout') {
      try {
        const data = await supabaseRpc(rpc, args);
        res.setHeader('Set-Cookie', clearSessionCookie());
        return json(res, 200, stripSessionToken(data));
      } catch (error) {
        res.setHeader('Set-Cookie', clearSessionCookie());
        throw error;
      }
    }

    const data = await supabaseRpc(rpc, args);
    return json(res, 200, stripSessionToken(data));
  } catch (error) {
    const message = String(error?.message || 'REQUEST_FAILED');
    const status = Number(error?.status || 500);
    if (status === 401 || /SESSION|TOKEN|UNAUTHORIZED/i.test(message)) {
      res.setHeader('Set-Cookie', clearSessionCookie());
    }
    return json(res, status >= 400 && status < 600 ? status : 500, { message });
  }
};
