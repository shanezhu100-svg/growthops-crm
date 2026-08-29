// Historical fail-closed probe entrypoint retained only to avoid rewriting the
// established finance test import chain. All executable assertions now live in
// the permanent regression module below; this file contains no probe behavior.
await import('./test_business_finance_visible_profit.mjs');
