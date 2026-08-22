-- P5 group 1 emergency rollback only.
-- Re-opens the two pre-P5 anon EXECUTE grants and nothing else.
-- Use only if Cloudflare/Vercel server-identity validation fails after revoke.

begin;

grant execute on function public.crm_unlock_credentials_v1(text, text) to anon;
grant execute on function public.crm_reveal_client_secret_value_v5(text, text, text, text, text, text) to anon;

commit;
