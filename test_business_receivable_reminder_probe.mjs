// Focused build entry retained for receivable/reminder regressions. Keep the
// persisted-mutation inventory on this root so every shipped write boundary remains
// reviewable from the protected business gate without adding a redundant root.
await import('./test_business_receivable_reminder_close.mjs');
await import('./test_business_persisted_mutation_inventory.mjs');
await import('./test_business_client_lifecycle_mutation_probe.mjs');
