# Current Recovery Bundle v3 Artifact

Accepted on 2026-08-27.

- workflow run: `33079493119`
- protected source: `main@89e1904a521c41ab1b35eb29ef25c2834bf76538`
- artifact: `growthops-schema-recovery-bundle-v3-33079493119`
- artifact ID: `9649406110`
- ZIP SHA-256: `c18833d5833239e330af686ad407d3dc472c499356651b2ff51bea36eb8876f7`
- artifact size: `22424` bytes
- files: `12`
- schema.sql: `100993` bytes / `37a49bb03df429b0e25fe0a52c3be5383bdac93b17d92ba7e257dd574fd748e2`
- post-schema-security.sql: `d811cfa142e2268b4ef4746f7bc87f837cc21b590b3716a3f834b68b36abbfe0`
- migration ledger: `51`, head `20260825075808 / post_p5_rate_limit_concurrency`
- event triggers: `4`
- service_role CRM RPC grants: `12`
- customer rows exported: `false`
- migration statement arrays exported: `false`
- supabase_admin defaults touched by recovery adjunct: `false`

Artifact integrity/scope is accepted. #93 remains open until a second truly fresh hosted target restores directly from this v3 artifact without manual repair and passes the full recovery acceptance.
