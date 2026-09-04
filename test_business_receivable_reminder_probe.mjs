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
await import('./test_business_opening_provider_mutations.mjs');
await import('./test_business_opening_provider_persistence_ack_probe.mjs');
await import('./test_business_client_reminder_money_mutations.mjs');
await import('./test_business_client_reminder_date_mutations.mjs');
await import('./test_business_bulk_receivable_generation.mjs');
await import('./test_business_ad_persisted_mutations.mjs');
await import('./test_business_ad_structure_mutations.mjs');
await import('./test_business_resource_catalog_mutations.mjs');