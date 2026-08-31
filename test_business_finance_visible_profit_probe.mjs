// Historical fail-closed probe entrypoint retained only to avoid rewriting the
// established finance test import chain. Permanent finance regressions execute below.
await import('./test_business_finance_visible_profit.mjs');
await import('./test_business_finance_archived_receivable_guard.mjs');
