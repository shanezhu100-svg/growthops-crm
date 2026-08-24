'use strict';

const { createHash } = require('node:crypto');

const SUPABASE_URL_DEFAULT = 'https://avahcwyxparbcjdfglzx.supabase.co';
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
  'crm_reveal_client_secret_value_v5',
]);

const ALL_RPCS = new Set([...PUBLIC_RPCS, ...LOGIN_RPCS, ...AUTH_RPCS]);
const SAFE_UPSTREAM_MESSAGES = new Set([
  'CREDENTIAL_REAUTH_REQUIRED',
  'CREDENTIAL_REVEAL_THROTTLED',
  'CREDENTIAL_UNLOCK_REQUIRED',
  'CREDENTIAL_UNLOCK_INVALID',
  'CREDENTIAL_UNLOCK_THROTTLED',
  'INVALID_CREDENTIAL_FIELD',
  'FORBIDDEN',
]);

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

function requestId(req) {
  const incoming = String(req.headers['x-request-id'] || '').trim();
  if (/^[A-Za-z0-9._:-]{8,128}$/.test(incoming)) return incoming;
  try {
    if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  } catch {}
  return `req-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function normalizeTrustedIp(raw) {
  const ip = String(raw || '').split(',')[0].trim().toLowerCase();
  if (!ip || ip.length > 64 || !/^[0-9a-f:.]+$/.test(ip)) return '';
  return ip;
}

function loginSourceBucket(req) {
  // Vercel overwrites the incoming x-forwarded-for value at its edge, so the
  // browser cannot choose this trust input. Only a truncated hash is forwarded.
  const ip = normalizeTrustedIp(req.headers['x-forwarded-for']);
  if (!ip) return '';
  return createHash('sha256').update(ip, 'utf8').digest('hex').slice(0, 24);
}

function supabaseOrigin(raw) {
  const value = String(raw || SUPABASE_URL_DEFAULT).trim();
  try {
    const parsed = new URL(value);
    const host = String(parsed.hostname || '').toLowerCase().replace(/\.$/, '');
    if (parsed.protocol !== 'https:' || !host.endsWith('.supabase.co')) return '';
    if (parsed.username || parsed.password || (parsed.port && parsed.port !== '443')) return '';
    if (parsed.pathname !== '/' || parsed.search || parsed.hash) return '';
    return `https://${host}`;
  } catch {
    return '';
  }
}

function serverConfig() {
  const key = String(process.env.GROWTHOPS_SUPABASE_SECRET_KEY || '').trim();
  const url = supabaseOrigin(process.env.GROWTHOPS_SUPABASE_URL);
  if (!/^sb_secret_[A-Za-z0-9_-]+$/.test(key) || !url) return null;
  return { url, key };
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

function safeLog(event, requestIdValue, rpc, status) {
  const safeRpc = ALL_RPCS.has(rpc) ? rpc : 'unknown';
  console.error(JSON.stringify({
    event,
    platform: 'vercel',
    requestId: requestIdValue,
    rpc: safeRpc,
    status: Number(status || 0),
  }));
}

function safeUpstreamMessage(data) {
  const message = String(data?.message || '').trim();
  return SAFE_UPSTREAM_MESSAGES.has(message) ? message : '';
}

async function supabaseRpc(name, args, config, sourceBucket = '') {
  const headers = {
    apikey: config.key,
    'Content-Type': 'application/json',
    'Cache-Control': 'no-store',
  };
  if (/^[0-9a-f]{24}$/.test(String(sourceBucket))) {
    headers['x-growthops-source-bucket'] = String(sourceBucket);
  }

  const response = await fetch(`${config.url}/rest/v1/rpc/${encodeURIComponent(name)}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(args || {}),
  });

  let data = null;
  try { data = await response.json(); } catch {}
  if (!response.ok) {
    const error = new Error('UPSTREAM_RPC_FAILED');
    error.status = response.status;
    error.safeMessage = safeUpstreamMessage(data);
    error.sessionRelated = /SESSION|TOKEN|UNAUTHORIZED/i.test(String(data?.message || data?.hint || ''));
    throw error;
  }
  return data;
}

function sanitizeUpstreamError(error) {
  const safeMessage = String(error?.safeMessage || '');
  if (safeMessage) {
    if (safeMessage.endsWith('_THROTTLED')) return { status: 429, message: safeMessage };
    if (safeMessage === 'FORBIDDEN') return { status: 403, message: safeMessage };
    return { status: 400, message: safeMessage };
  }
  const status = Number(error?.status || 0);
  if (status === 400) return { status: 400, message: 'UPSTREAM_BAD_REQUEST' };
  if (status === 401) return { status: 401, message: 'SESSION_INVALID' };
  if (status === 403) return { status: 403, message: 'REQUEST_DENIED' };
  if (status === 404) return { status: 404, message: 'UPSTREAM_NOT_FOUND' };
  if (status === 409) return { status: 409, message: 'CONFLICT' };
  if (status === 429) return { status: 429, message: 'RATE_LIMITED' };
  return { status: 502, message: 'UPSTREAM_REQUEST_FAILED' };
}

function stripSessionToken(data) {
  if (!data || typeof data !== 'object' || Array.isArray(data)) return data;
  if (!Object.prototype.hasOwnProperty.call(data, 'token')) return data;
  const safe = { ...data };
  delete safe.token;
  return safe;
}

module.exports = async function handler(req, res) {
  const requestIdValue = requestId(req);
  res.setHeader('X-Request-ID', requestIdValue);

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

  const config = serverConfig();
  if (!config) {
    safeLog('server_identity_missing', requestIdValue, rpc, 503);
    return json(res, 503, { message: 'SERVER_IDENTITY_NOT_CONFIGURED' });
  }

  const cookies = parseCookies(req.headers.cookie || '');
  const sessionToken = String(cookies[COOKIE_NAME] || '');

  try {
    if (LOGIN_RPCS.has(rpc)) {
      delete args.p_token;
      const data = await supabaseRpc(rpc, args, config, loginSourceBucket(req));
      if (data?.error) return json(res, 401, { message: 'LOGIN_FAILED' });
      const token = String(data?.token || '');
      if (!token) return json(res, 502, { message: 'LOGIN_SESSION_MISSING' });
      res.setHeader('Set-Cookie', sessionCookie(token));
      return json(res, 200, stripSessionToken(data));
    }

    if (PUBLIC_RPCS.has(rpc)) {
      delete args.p_token;
      return json(res, 200, stripSessionToken(await supabaseRpc(rpc, args, config)));
    }

    if (!sessionToken) {
      res.setHeader('Set-Cookie', clearSessionCookie());
      return json(res, 401, { message: 'SESSION_REQUIRED' });
    }

    args.p_token = sessionToken;

    if (rpc === 'crm_logout') {
      try {
        const data = await supabaseRpc(rpc, args, config);
        res.setHeader('Set-Cookie', clearSessionCookie());
        return json(res, 200, stripSessionToken(data));
      } catch (error) {
        res.setHeader('Set-Cookie', clearSessionCookie());
        throw error;
      }
    }

    const data = await supabaseRpc(rpc, args, config);
    return json(res, 200, stripSessionToken(data));
  } catch (error) {
    const upstreamStatus = Number(error?.status || 0);
    if (upstreamStatus === 401 || error?.sessionRelated) {
      res.setHeader('Set-Cookie', clearSessionCookie());
    }
    const safe = sanitizeUpstreamError(error);
    safeLog('upstream_rpc_error', requestIdValue, rpc, upstreamStatus || safe.status);
    return json(res, safe.status, { message: safe.message });
  }
};
