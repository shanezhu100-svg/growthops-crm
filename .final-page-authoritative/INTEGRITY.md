# Final CRM authoritative source integrity

- Authoritative source: `digital_marketing_crm_predeploy_audited_fixed.html`
- Raw UTF-8 source length: **510,961 bytes**
- JSON-escaped serialization length: **643,031 characters**
- Canonical source chain: contiguous `offset-START-END.htmlpart` files covering **0 → 510,961**
- Verification: every canonical part was checked against the corresponding byte range of the authoritative source; reconstructed bytes match the authoritative source exactly, including SHA-256 equality.
- Canonical final part: `offset-500200-510961.htmlpart`
- Exclude historical misnamed part: `offset-500200-516200.htmlpart` (its filename end offset is not authoritative and it must not be used for reconstruction).

Do not use legacy `.cloud`, `app/part-*`, `.final-page-html`, or the excluded misnamed part when reconstructing the final confirmed CRM page.
