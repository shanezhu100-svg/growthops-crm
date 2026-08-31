// Historical fail-closed probe entrypoint retained only to avoid rewriting the
// established finance test import chain. All executable assertions now live in
// the permanent regression module below; this file contains no production probe behavior.
await import('./test_business_finance_visible_profit.mjs');
await import('./probe_archived_receivable_runtime.mjs');
