const SUPABASE_URL_DEFAULT = 'https://avahcwyxparbcjdfglzx.supabase.co';
const SUPABASE_KEY_DEFAULT = 'sb_publishable_5Wkk8Bb1zh5lB1YEnvJBPg_Uvmtv62w';
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

function sameOrigin(request) {
  const site = String(request.headers.get('sec-fetch-site') || '').toLowerCase();
  if (site && site !== 'same-origin' && site !== 'none') return false;

  const origin = String(request.headers.get('origin') || '');
  if (!origin) return true;

  let requestOrigin = '';
  try { requestOrigin = new URL(request.url).origin; } catch { return false; }
  return origin === requestOrigin;
}

function json(status, body, extraHeaders = {}) {
  const headers = new Headers({
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store, max-age=0',
    'Pragma': 'no-cache',
    ...extraHeaders,
  });
  return new Response(JSON.stringify(body), { status, headers });
}

async function bodyObject(request) {
  const text = await request.text();
  if (!text) return {};
  try {
    const parsed = JSON.parse(text);
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : parsed;
  } catch {
    return null;
  }
}

async function supabaseRpc(name, args, env = {}) {
  const supabaseUrl = env.GROWTHOPS_SUPABASE_URL || SUPABASE_URL_DEFAULT;
  const supabaseKey = env.GROWTHOPS_SUPABASE_PUBLISHABLE_KEY || SUPABASE_KEY_DEFAULT;
  const response = await fetch(`${supabaseUrl}/rest/v1/rpc/${encodeURIComponent(name)}`, {
    method: 'POST',
    headers: {
      apikey: supabaseKey,
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

export async function onRequest(context) {
  const request = context.request;
  const env = context.env || {};

  if (request.method !== 'POST') {
    return json(405, { message: 'METHOD_NOT_ALLOWED' }, { Allow: 'POST' });
  }
  if (!sameOrigin(request)) return json(403, { message: 'CROSS_ORIGIN_REQUEST_BLOCKED' });

  const body = await bodyObject(request);
  if (!body) return json(400, { message: 'INVALID_JSON' });

  const rpc = String(body.rpc || '');
  const args = body.args && typeof body.args === 'object' && !Array.isArray(body.args) ? { ...body.args } : {};
  if (!ALL_RPCS.has(rpc)) return json(403, { message: 'RPC_NOT_ALLOWED' });

  const cookies = parseCookies(request.headers.get('cookie') || '');
  const sessionToken = String(cookies[COOKIE_NAME] || '');

  try {
    if (LOGIN_RPCS.has(rpc)) {
      delete args.p_token;
      const data = await supabaseRpc(rpc, args, env);
      if (data?.error) return json(401, { message: String(data.error) });
      const token = String(data?.token || '');
      if (!token) return json(502, { message: 'LOGIN_SESSION_MISSING' });
      return json(200, stripSessionToken(data), { 'Set-Cookie': sessionCookie(token) });
    }

    if (PUBLIC_RPCS.has(rpc)) {
      delete args.p_token;
      return json(200, stripSessionToken(await supabaseRpc(rpc, args, env)));
    }

    if (!sessionToken) {
      return json(401, { message: 'SESSION_REQUIRED' }, { 'Set-Cookie': clearSessionCookie() });
    }

    args.p_token = sessionToken;

    if (rpc === 'crm_logout') {
      try {
        const data = await supabaseRpc(rpc, args, env);
        return json(200, stripSessionToken(data), { 'Set-Cookie': clearSessionCookie() });
      } catch (error) {
        error.clearSessionCookie = true;
        throw error;
      }
    }

    const data = await supabaseRpc(rpc, args, env);
    return json(200, stripSessionToken(data));
  } catch (error) {
    const message = String(error?.message || 'REQUEST_FAILED');
    const status = Number(error?.status || 500);
    const headers = {};
    if (error?.clearSessionCookie || status === 401 || /SESSION|TOKEN|UNAUTHORIZED/i.test(message)) {
      headers['Set-Cookie'] = clearSessionCookie();
    }
    return json(status >= 400 && status < 600 ? status : 500, { message }, headers);
  }
}
