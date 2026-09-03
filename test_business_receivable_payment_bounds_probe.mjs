// Compatibility entry retained to avoid unnecessary build.sh churn while finance
// payment regressions are expanded. Each focused test executes the final shipped code.
import './test_business_receivable_payment_bounds.mjs';
import './test_business_receivable_payment_date_probe.mjs';
import './destructive_confirmation_source_probe.mjs';
import './test_business_destructive_confirmation_toctou_probe.mjs';
