// Focused build entry retained for receivable/reminder regressions. Keep the
// persisted-mutation inventory and focused mutation regressions on this root so
// shipped write boundaries remain reviewable without adding redundant roots.
await import('./test_business_receivable_reminder_close.mjs');
await import('./test_business_persisted_mutation_inventory.mjs');
await import('./test_business_client_lifecycle_mutations.mjs');
await import('./test_business_finance_settlement_mutations.mjs');
await import('./test_business_finance_cost_mutations.mjs');
await import('./test_business_opening_cost_month_lock.mjs');
await import('./test_business_opening_deal_mutations.mjs');