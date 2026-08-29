// Historical fail-closed inventory probe has served its purpose. Keep this tiny
// chain shim so the established business-regression import path remains stable.
await import('./test_business_analytics_semantics.mjs');
