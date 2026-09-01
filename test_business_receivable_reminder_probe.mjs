// Focused build entry retained for receivable/reminder regressions. Keep the
// persisted-mutation inventory and client-lifecycle mutation regression on this root
// so shipped write boundaries remain reviewable without adding redundant roots.
await import('./test_business_receivable_reminder_close.mjs');
await import('./test_business_persisted_mutation_inventory.mjs');
await import('./test_business_client_lifecycle_mutations.mjs');
