begin;

create schema if not exists private;

create or replace function private.agp_is_self_participant(
  target_participant uuid,
  target_athlete uuid,
  target_project uuid
)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.agp_contas_acesso ca
    join public.agp_participantes_projeto pp on pp.pessoa_id = ca.pessoa_id
    join public.agp_perfis_esportivos pe on pe.pessoa_id = ca.pessoa_id
    where ca.auth_id = (select auth.uid())
      and ca.status = 'ativo'
      and pp.id = target_participant
      and pp.projeto_id = target_project
      and pp.funcao_no_projeto = 'atleta'
      and pp.ativo = true
      and pe.legacy_perfil_atleta_id = target_athlete
      and pe.status = 'ativo'
  );
$$;

revoke all on function private.agp_is_self_participant(uuid, uuid, uuid) from public;
grant usage on schema private to authenticated;
grant execute on function private.agp_is_self_participant(uuid, uuid, uuid) to authenticated;

alter table public.agp_coletas enable row level security;

drop policy if exists agp_coletas_access on public.agp_coletas;
drop policy if exists agp_coletas_select_v2 on public.agp_coletas;
drop policy if exists agp_coletas_insert_v2 on public.agp_coletas;
drop policy if exists agp_coletas_update_v2 on public.agp_coletas;

create policy agp_coletas_select_v2
on public.agp_coletas
for select
to authenticated
using (
  public.agp_is_owner()
  or (projeto_id is not null and public.agp_athlete_project_access(atleta_id, projeto_id))
  or private.agp_is_self_participant(participante_id, atleta_id, projeto_id)
);

create policy agp_coletas_insert_v2
on public.agp_coletas
for insert
to authenticated
with check (
  public.agp_is_owner()
  or (projeto_id is not null and public.agp_athlete_project_access(atleta_id, projeto_id))
  or (
    origem = 'autodeclarado'
    and coletado_por_auth_id = (select auth.uid())
    and private.agp_is_self_participant(participante_id, atleta_id, projeto_id)
  )
);

create policy agp_coletas_update_v2
on public.agp_coletas
for update
to authenticated
using (
  public.agp_is_owner()
  or (projeto_id is not null and public.agp_athlete_project_access(atleta_id, projeto_id))
)
with check (
  public.agp_is_owner()
  or (projeto_id is not null and public.agp_athlete_project_access(atleta_id, projeto_id))
);

commit;
