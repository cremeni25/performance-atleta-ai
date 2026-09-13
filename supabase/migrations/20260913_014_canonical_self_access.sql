begin;

drop policy if exists agp_contas_self_select on public.agp_contas_acesso;
create policy agp_contas_self_select
on public.agp_contas_acesso
for select
to authenticated
using (
  auth_id = (select auth.uid())
  or (
    auth_id is null
    and status = 'acesso_pendente'
    and lower(email_acesso) = lower((select auth.jwt() ->> 'email'))
  )
);

drop policy if exists agp_contas_self_claim on public.agp_contas_acesso;
create policy agp_contas_self_claim
on public.agp_contas_acesso
for update
to authenticated
using (
  auth_id is null
  and status = 'acesso_pendente'
  and lower(email_acesso) = lower((select auth.jwt() ->> 'email'))
)
with check (
  auth_id = (select auth.uid())
  and status = 'ativo'
  and lower(email_acesso) = lower((select auth.jwt() ->> 'email'))
);

drop policy if exists agp_pessoas_self_read on public.agp_pessoas;
create policy agp_pessoas_self_read
on public.agp_pessoas
for select
to authenticated
using (
  exists (
    select 1
    from public.agp_contas_acesso ca
    where ca.pessoa_id = agp_pessoas.id
      and ca.auth_id = (select auth.uid())
      and ca.status = 'ativo'
  )
);

drop policy if exists agp_participantes_self_read on public.agp_participantes_projeto;
create policy agp_participantes_self_read
on public.agp_participantes_projeto
for select
to authenticated
using (
  exists (
    select 1
    from public.agp_contas_acesso ca
    where ca.pessoa_id = agp_participantes_projeto.pessoa_id
      and ca.auth_id = (select auth.uid())
      and ca.status = 'ativo'
  )
);

drop policy if exists agp_perfis_self_read on public.agp_perfis_esportivos;
create policy agp_perfis_self_read
on public.agp_perfis_esportivos
for select
to authenticated
using (
  exists (
    select 1
    from public.agp_contas_acesso ca
    where ca.pessoa_id = agp_perfis_esportivos.pessoa_id
      and ca.auth_id = (select auth.uid())
      and ca.status = 'ativo'
  )
);

drop policy if exists agp_consentimentos_self_read on public.agp_consentimentos;
create policy agp_consentimentos_self_read
on public.agp_consentimentos
for select
to authenticated
using (
  exists (
    select 1
    from public.agp_participantes_projeto pp
    join public.agp_contas_acesso ca on ca.pessoa_id = pp.pessoa_id
    where pp.id = agp_consentimentos.participante_id
      and ca.auth_id = (select auth.uid())
      and ca.status = 'ativo'
  )
);

drop policy if exists agp_ativacoes_self_read on public.agp_ativacoes_instrumentos;
create policy agp_ativacoes_self_read
on public.agp_ativacoes_instrumentos
for select
to authenticated
using (
  exists (
    select 1
    from public.agp_participantes_projeto pp
    join public.agp_contas_acesso ca on ca.pessoa_id = pp.pessoa_id
    where pp.projeto_id = agp_ativacoes_instrumentos.projeto_id
      and pp.ativo = true
      and ca.auth_id = (select auth.uid())
      and ca.status = 'ativo'
  )
);

commit;
