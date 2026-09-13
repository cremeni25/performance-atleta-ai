begin;

drop policy if exists agp_contas_invited_activate on public.agp_contas_acesso;
create policy agp_contas_invited_activate
on public.agp_contas_acesso
for update
to authenticated
using (
  auth_id = (select auth.uid())
  and status = 'acesso_pendente'
  and lower(email_acesso) = lower((select auth.jwt() ->> 'email'))
)
with check (
  auth_id = (select auth.uid())
  and status = 'ativo'
  and lower(email_acesso) = lower((select auth.jwt() ->> 'email'))
);

commit;
