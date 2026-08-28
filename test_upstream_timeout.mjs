import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';

const TEST_SECRET = 'sb_secret_test_upstream_timeout_20260827';
const require = createRequire(import.meta.url);
const vercelHandler = require('./api/crm.js');
const cfSource = readFileSync(new URL('./functions/api/crm.js', import.meta.url), 'utf8');
const { onRequest: cloudflareHandler } = await import(`data:text/javascript;base64,${Buffer.from(cfSource).toString('base64')}`);

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

function parse(text) {
  try { return JSON.parse(text); } catch { return null; }
}

const original = {
  fetch: global.fetch,
  setTimeout: global.setTimeout,
  clearTimeout: global.clearTimeout,
  consoleError: console.error,
};
const envNames = ['GROWTHOPS_SUPABASE_SECRET_KEY', 'GROWTHOPS_SUPABASE_URL', 'VERCEL_ENV'];
const oldEnv = Object.fromEntries(envNames.map(name => [name, process.env[name]]));
const timeoutValues = [];
let clearCount = 0;
const logs = [];

function installSyntheticHungUpstream() {
  global.setTimeout = (callback, milliseconds) => {
    timeoutValues.push(Number(milliseconds));
    queueMicrotask(callback);
    return Symbol('synthetic-timeout');
  };
  global.clearTimeout = () => { clearCount += 1; };
  global.fetch = async (_url, options = {}) => new Promise((resolve, reject) => {
    const signal = options.signal;
    assert.ok(signal, 'upstream fetch must receive an AbortSignal');
    const abort = () => {
      const error = new Error('synthetic upstream timeout');
      error.name = 'AbortError';
      reject(error);
    };
    if (signal.aborted) abort();
    else signal.addEventListener('abort', abort, { once: true });
  });
  console.error = (...args) => logs.push(args.join(' '));
}

try {
  installSyntheticHungUpstream();

  process.env.GROWTHOPS_SUPABASE_SECRET_KEY = TEST_SECRET;
  delete process.env.GROWTHOPS_SUPABASE_URL;
  process.env.VERCEL_ENV = 'production';

  const vercelRes = makeRes();
  await vercelHandler({
    method: 'POST',
    headers: {
      'sec-fetch-site': 'same-origin',
      origin: 'https://timeout.example',
      host: 'timeout.example',
      'x-forwarded-host': 'timeout.example',
      'x-forwarded-proto': 'https',
    },
    body: { rpc: 'crm_public_status', args: {} },
  }, vercelRes);
  assert.equal(vercelRes.statusCode, 502);
  assert.deepEqual(parse(vercelRes.body), { message: 'UPSTREAM_REQUEST_FAILED' });

  const request = new Request('https://growthops-crm.pages.dev/api/crm', {
    method: 'POST',
    headers: {
      'sec-fetch-site': 'same-origin',
      origin: 'https://growthops-crm.pages.dev',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ rpc: 'crm_public_status', args: {} }),
  });
  const cfResponse = await cloudflareHandler({
    request,
    env: { GROWTHOPS_SUPABASE_SECRET_KEY: TEST_SECRET },
  });
  assert.equal(cfResponse.status, 502);
  assert.deepEqual(await cfResponse.json(), { message: 'UPSTREAM_REQUEST_FAILED' });

  assert.deepEqual(timeoutValues, [15000, 15000], 'both BFFs must use the same 15-second upstream timeout');
  assert.equal(clearCount, 2, 'both BFFs must clear their timeout handle');
  assert.ok(logs.every(line => !line.includes(TEST_SECRET)), 'timeout logs must not contain server identity');
  assert.ok(logs.filter(line => line.includes('upstream_rpc_error')).length >= 2, 'both BFFs must use the sanitized upstream error path');
} finally {
  global.fetch = original.fetch;
  global.setTimeout = original.setTimeout;
  global.clearTimeout = original.clearTimeout;
  console.error = original.consoleError;
  for (const name of envNames) {
    if (oldEnv[name] === undefined) delete process.env[name];
    else process.env[name] = oldEnv[name];
  }
}

console.log('UPSTREAM_TIMEOUT_OK: vercel=15s-abort->502; cloudflare=15s-abort->502; timeout-handle=cleared; server-identity=not-logged');
