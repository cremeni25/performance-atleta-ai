begin;

revoke update on public.agp_contas_acesso from authenticated;
grant update (auth_id,status,primeiro_acesso_em,ultimo_acesso_em,updated_at)
on public.agp_contas_acesso
to authenticated;

commit;
