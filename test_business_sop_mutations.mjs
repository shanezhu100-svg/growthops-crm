import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root = process.cwd();
const appDir = path.join(root, 'dist', 'app');
if (!fs.existsSync(appDir)) throw new Error('BUSINESS_SOP_MUTATIONS_FAILED: dist/app missing');
const files = fs.readdirSync(appDir).filter(name => /^app-inline-\d+\.js$/.test(name)).sort();
if (!files.length) throw new Error('BUSINESS_SOP_MUTATIONS_FAILED: no final app-inline JS artifacts');
const bundle = files.map(name => fs.readFileSync(path.join(appDir, name), 'utf8')).join('\n');

function extractMethod(name) {
  const signature = new RegExp(`(?:^|[,\\n])\\s*(${name}\\([^)]*\\)\\s*\\{)`, 'm');
  const match = signature.exec(bundle);
  if (!match) throw new Error(`BUSINESS_SOP_MUTATIONS_FAILED: ${name} not found`);
  const start = match.index + match[0].indexOf(match[1]);
  const tail = bundle.slice(start);
  const defs = [...tail.matchAll(/(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{/g)];
  if (defs.length < 2 || defs[0][1] !== name) throw new Error(`BUSINESS_SOP_MUTATIONS_FAILED: ${name} parser drifted`);
  const next = defs[1].index + defs[1][0].indexOf(defs[1][1]);
  return tail.slice(0, next).replace(/,\s*$/, '').trim();
}

const names = ['ensureSopDailyTasks', 'removeSopStep', 'saveSopDailyTasks', 'saveSopSettings', 'saveSopTask'];
const storage = new Map();
const localStorage = {
  getItem(key) { return storage.has(String(key)) ? storage.get(String(key)) : null; },
  setItem(key, value) { storage.set(String(key), String(value)); },
  removeItem(key) { storage.delete(String(key)); },
  clear() { storage.clear(); },
};
const context = { String, Number, Boolean, Array, Object, JSON, Math, Date, localStorage };
const methods = vm.runInNewContext(`({${names.map(extractMethod).join(',')}})`, context, { timeout: 1000 });
for (const name of names) if (typeof methods[name] !== 'function') throw new Error(`BUSINESS_SOP_MUTATIONS_FAILED: ${name} not executable`);

const fail = (label, expected, actual) => { throw new Error(`BUSINESS_SOP_MUTATIONS_FAILED: ${label}; expected=${expected}; actual=${actual}`); };
const eq = (actual, expected, label) => { if (actual !== expected) fail(label, expected, actual); };
const jsonEq = (actual, expected, label) => {
  const a = JSON.stringify(actual), e = JSON.stringify(expected);
  if (a !== e) fail(label, e, a);
};
const count = (calls, type) => calls.filter(call => call[0] === type).length;

function makeSubject({ cfg, today = '2026-09-03', date = today, form = {}, overrides = {} } = {}) {
  storage.clear();
  let uid = 0;
  const calls = [];
  const config = cfg || { steps: [], dailyTasks: {}, dailyPlan: '', notes: '' };
  const target = {
    selectedSopDate: date,
    selectedSopClient: { id: 'client-1', name: 'Alpha' },
    selectedSopClientId: 'client-1',
    selectedSopAccount: { platform: 'FB', account: { id: 'account-1', accountName: 'Primary', adAccountId: 'act-1' } },
    selectedSopAccountKey: 'FB:account-1',
    sopSelectedDateBadge: date,
    sopTaskForm: { id: '', originalDate: '', date, text: '', plan: '', note: '', ...form },
    sopChecked: {},
    sopExpandedTasks: {},
    showSopTaskModal: true,
    ensureSelectedSopConfig: () => config,
    accountUid: prefix => `${prefix}-${++uid}`,
    localDateKey: () => today,
    persist: () => calls.push(['persist']),
    logAudit: (...args) => calls.push(['audit', ...args]),
    notify: (...args) => calls.push(['notify', ...args]),
    askConfirm: (spec, callback) => { calls.push(['confirm', spec]); target.confirmCallback = callback; },
    saveSopProgress: () => calls.push(['progress-save']),
    loadSopProgress: () => calls.push(['progress-load']),
    ...methods,
    ...overrides,
  };
  return { subject: target, cfg: config, calls };
}

// Lazy daily-task initialization must copy only meaningful template rows and write once.
{
  const cfg = { steps: [{ text: 'Launch', plan: 'P', note: '' }, { text: '', plan: '', note: '' }], dailyTasks: {} };
  const { subject, calls } = makeSubject({ cfg, date: '2026-09-04' });
  const first = subject.ensureSopDailyTasks('2026-09-04');
  eq(first.length, 1, 'daily task initialization filters empty template rows');
  eq(first[0].text, 'Launch', 'daily task initialization preserves text');
  eq(count(calls, 'persist'), 1, 'daily task initialization persists exactly once');
  const second = subject.ensureSopDailyTasks('2026-09-04');
  eq(second, first, 'existing daily task array is reused');
  eq(count(calls, 'persist'), 1, 'existing daily task array does not persist again');
}

// Daily checklist save normalizes values, refreshes today template, and writes once.
{
  const cfg = { steps: [], dailyTasks: { '2026-09-03': [{ id: 'task-1', text: 123, plan: null, note: ' note ' }] } };
  const { subject, calls } = makeSubject({ cfg });
  subject.saveSopDailyTasks();
  jsonEq(cfg.dailyTasks['2026-09-03'], [{ id: 'task-1', text: '123', plan: '', note: ' note ' }], 'daily checklist normalized');
  eq(cfg.steps.length, 1, 'today checklist refreshes template');
  eq(cfg.steps[0].text, '123', 'today template text normalized');
  eq(count(calls, 'persist'), 1, 'daily checklist save persists once');
}

// Settings save trims durable text and keeps persist/audit/notice semantics.
{
  const cfg = { steps: [], dailyTasks: {}, dailyPlan: '  plan  ', notes: '  notes  ' };
  const { subject, calls } = makeSubject({ cfg });
  subject.saveSopSettings();
  eq(cfg.dailyPlan, 'plan', 'daily plan trimmed');
  eq(cfg.notes, 'notes', 'notes trimmed');
  eq(count(calls, 'persist'), 1, 'settings persist once');
  eq(count(calls, 'audit'), 1, 'settings audit once');
  eq(count(calls, 'notify'), 1, 'settings notify once');
}

// New task path remains a single durable write; blank task is denied without mutation.
{
  const cfg = { steps: [], dailyTasks: { '2026-09-03': [] } };
  const { subject, calls } = makeSubject({ cfg, form: { text: '  New task  ', plan: ' P ', note: ' N ' } });
  subject.saveSopTask();
  eq(cfg.dailyTasks['2026-09-03'].length, 1, 'new task appended');
  eq(cfg.dailyTasks['2026-09-03'][0].text, 'New task', 'new task text trimmed');
  eq(count(calls, 'persist'), 1, 'new task persists once');
  eq(count(calls, 'audit'), 1, 'new task audits once');
  eq(count(calls, 'progress-load'), 1, 'new task reloads progress once');
  eq(subject.showSopTaskModal, false, 'new task closes modal');
}
{
  const cfg = { steps: [], dailyTasks: { '2026-09-03': [] } };
  const { subject, calls } = makeSubject({ cfg, form: { text: '   ' } });
  subject.saveSopTask();
  eq(cfg.dailyTasks['2026-09-03'].length, 0, 'blank task does not append');
  eq(count(calls, 'persist'), 0, 'blank task does not persist');
  eq(count(calls, 'audit'), 0, 'blank task does not audit');
  eq(count(calls, 'notify'), 1, 'blank task reports validation');
}

// Editing must be compare-and-set against an existing task. A stale editor must not
// create the missing day from the template or resurrect the deleted task ID.
{
  const cfg = { steps: [{ id: 'template-1', text: 'Template', plan: '', note: '' }], dailyTasks: {} };
  const { subject, calls } = makeSubject({
    cfg,
    date: '2026-09-04',
    form: { id: 'deleted-task', originalDate: '2026-09-04', date: '2026-09-04', text: 'Stale edit' },
  });
  subject.saveSopTask();
  eq(Object.prototype.hasOwnProperty.call(cfg.dailyTasks, '2026-09-04'), false, 'stale edit does not initialize missing original day');
  eq(count(calls, 'persist'), 0, 'stale edit does not persist');
  eq(count(calls, 'audit'), 0, 'stale edit does not audit');
  eq(count(calls, 'progress-load'), 0, 'stale edit does not reload progress');
  eq(count(calls, 'notify'), 1, 'stale edit reports missing task');
}

// A live edit keeps task identity and normal mutation semantics.
{
  const cfg = { steps: [], dailyTasks: { '2026-09-03': [{ id: 'task-1', text: 'Old', plan: '', note: '' }] } };
  const { subject, calls } = makeSubject({ cfg, form: { id: 'task-1', originalDate: '2026-09-03', text: 'Updated' } });
  subject.saveSopTask();
  jsonEq(cfg.dailyTasks['2026-09-03'].map(x => [x.id, x.text]), [['task-1', 'Updated']], 'live edit preserves id and updates text');
  eq(count(calls, 'persist'), 1, 'live edit persists once');
  eq(count(calls, 'audit'), 1, 'live edit audits once');
}

// Delete confirmation must resolve by task identity, not the stale array index.
{
  const cfg = { steps: [], dailyTasks: { '2026-09-03': [
    { id: 'task-1', text: 'First', plan: '', note: '' },
    { id: 'task-2', text: 'Second', plan: '', note: '' },
  ] } };
  const { subject, calls } = makeSubject({ cfg });
  subject.removeSopStep(0);
  eq(count(calls, 'confirm'), 1, 'delete requests confirmation');
  const live = cfg.dailyTasks['2026-09-03'];
  live.splice(0, 2, live[1], live[0]);
  subject.confirmCallback();
  jsonEq(cfg.dailyTasks['2026-09-03'].map(x => x.id), ['task-2'], 'reordered confirmation deletes original task id');
  eq(count(calls, 'persist'), 1, 'live confirmed delete persists once');
  eq(count(calls, 'audit'), 1, 'live confirmed delete audits once');
  eq(count(calls, 'progress-save'), 1, 'live confirmed delete saves progress once');
}

// If the task disappears or the selected SOP context changes while confirmation is
// open, the callback must fail closed without persistence/audit/progress mutation.
{
  const cfg = { steps: [], dailyTasks: { '2026-09-03': [
    { id: 'task-1', text: 'First', plan: '', note: '' },
    { id: 'task-2', text: 'Second', plan: '', note: '' },
  ] } };
  const { subject, calls } = makeSubject({ cfg });
  subject.removeSopStep(0);
  cfg.dailyTasks['2026-09-03'] = [{ id: 'task-2', text: 'Second', plan: '', note: '' }];
  subject.confirmCallback();
  jsonEq(cfg.dailyTasks['2026-09-03'].map(x => x.id), ['task-2'], 'missing confirm target leaves live tasks unchanged');
  eq(count(calls, 'persist'), 0, 'missing confirm target does not persist');
  eq(count(calls, 'audit'), 0, 'missing confirm target does not audit');
  eq(count(calls, 'progress-save'), 0, 'missing confirm target does not save progress');
}
{
  const cfg = { steps: [], dailyTasks: { '2026-09-03': [{ id: 'task-1', text: 'First', plan: '', note: '' }] } };
  const { subject, calls } = makeSubject({ cfg });
  subject.removeSopStep(0);
  subject.selectedSopClient = { id: 'client-2', name: 'Beta' };
  subject.selectedSopClientId = 'client-2';
  subject.confirmCallback();
  eq(cfg.dailyTasks['2026-09-03'].length, 1, 'changed context leaves original task unchanged');
  eq(count(calls, 'persist'), 0, 'changed context does not persist');
  eq(count(calls, 'audit'), 0, 'changed context does not audit');
  eq(count(calls, 'progress-save'), 0, 'changed context does not save progress');
}

console.log('BUSINESS_SOP_MUTATIONS_OK: ensure=lazy-single-write; daily-save=normalized+today-template; settings=trim+persist+audit; task=create+live-edit+stale-edit-deny; delete=id-recheck+context-recheck; provenance=final-shipped-vm');
