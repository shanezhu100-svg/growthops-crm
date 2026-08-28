import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const vercel = readFileSync(new URL('./api/crm.js', import.meta.url), 'utf8');
const cloudflare = readFileSync(new URL('./functions/api/crm.js', import.meta.url), 'utf8');

function quotedSet(source, name) {
  const pattern = new RegExp(`const\\s+${name}\\s*=\\s*new Set\\((\\[[\\s\\S]*?\\])\\);`);
  const match = source.match(pattern);
  assert.ok(match, `${name} declaration missing`);
  const values = [...match[1].matchAll(/['"]([^'"]+)['"]/g)].map(m => m[1]).sort();
  assert.ok(values.length > 0, `${name} unexpectedly empty`);
  return values;
}

function literal(source, name) {
  const match = source.match(new RegExp(`const\\s+${name}\\s*=\\s*([^;]+);`));
  assert.ok(match, `${name} declaration missing`);
  return match[1].replace(/\\s+/g, ' ').trim();
}

for (const name of [
  'SUPABASE_URL_DEFAULT',
  'COOKIE_NAME',
  'COOKIE_MAX_AGE',
  'MAX_BODY_BYTES',
  'LOGIN_USERNAME_MAX_BYTES',
  'LOGIN_PASSWORD_MAX_BYTES',
]) {
  assert.equal(literal(vercel, name), literal(cloudflare, name), `${name} drifted between BFFs`);
}

for (const name of ['PUBLIC_RPCS', 'LOGIN_RPCS', 'AUTH_RPCS', 'SAFE_UPSTREAM_MESSAGES']) {
  assert.deepEqual(quotedSet(vercel, name), quotedSet(cloudflare, name), `${name} drifted between BFFs`);
}

const expectedPublic = ['crm_public_status'];
const expectedLogin = ['crm_login_v3'];
const expectedAuth = [
  'crm_client_account_safe_summary',
  'crm_delete_user',
  'crm_list_users',
  'crm_load_state_v3',
  'crm_logout',
  'crm_reveal_client_secret_value_v5',
  'crm_save_state',
  'crm_unlock_credentials_v1',
  'crm_upsert_user',
].sort();
assert.deepEqual(quotedSet(vercel, 'PUBLIC_RPCS'), expectedPublic);
assert.deepEqual(quotedSet(vercel, 'LOGIN_RPCS'), expectedLogin);
assert.deepEqual(quotedSet(vercel, 'AUTH_RPCS'), expectedAuth);

for (const [label, source, markers] of [
  ['Vercel', vercel, [
    "isProduction = environment === 'production'",
    'isProduction && url !== SUPABASE_URL_DEFAULT',
    "headers['x-growthops-source-bucket']",
    "delete args.p_token",
    'args.p_token = sessionToken',
    "'Cache-Control', 'no-store, max-age=0'",
  ]],
  ['Cloudflare', cloudflare, [
    'isPagesProduction=requestHost===CLOUDFLARE_PRODUCTION_HOST',
    'isPagesProduction&&url!==SUPABASE_URL_DEFAULT',
    "headers['x-growthops-source-bucket']",
    'delete args.p_token',
    'args.p_token=sessionToken',
    "'Cache-Control':'no-store, max-age=0'",
  ]],
]) {
  for (const marker of markers) assert.ok(source.includes(marker), `${label} missing shared security marker: ${marker}`);
}

console.log('BFF_SECURITY_SEMANTIC_PARITY_OK: constants=6; rpc-surfaces=1/1/9; safe-upstream-messages=aligned; production-pin/session/source-bucket/cache-markers=present');
