# Final confirmed CRM source integrity

- Authoritative source: `digital_marketing_crm_predeploy_audited_fixed.html`
- Raw UTF-8 bytes: **643031**
- SHA-256: `51ca745531e98d1799d0ac181e97e29a1fdd6ea2eb77587b41051d9519103e43`
- Canonical directory: `.final-page-canonical/`
- Canonical rule: only `offset-START-END.htmlpart` files in this directory are source chunks.
- Required coverage: exactly `0 -> 643031`, no gaps and no overlaps.
- Every chunk's Git blob SHA was recomputed from the authoritative file before this tree was created.
- Legacy directories (`.final-page-authoritative`, `.final-page-html`, `.final-page-encoded`, `.final-page-fragments`, `app/`) are historical only and MUST NOT be used for reconstruction.

Run `python3 verify_final_source.py` before any staging/production build.
