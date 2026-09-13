begin;

alter table public.agp_coletas enable row level security;

drop policy if exists agp_coletas_access on public.agp_coletas;
drop policy if exists agp_coletas_self_select on public.agp_coletas;
drop policy if exists agp_coletas_self_insert on public.agp_coletas;
drop policy if exists agp_coletas_staff_update on public.agp_coletas;

create policy agp_coletas_self_select
on public.agp_coletas
for select
to authenticated
using (
  public.agp_is_owner()
  or (
    projeto_id is not null
    and public.agp_user_can_access_institution(public.agp_project_institution(projeto_id))
  )
  or exists (
    select 1
    from public.agp_contas_acesso ca
    join public.agp_participantes_projeto pp on pp.pessoa_id = ca.pessoa_id
    join public.agp_perfis_esportivos pe on pe.pessoa_id = ca.pessoa_id
    where ca.auth_id = (select auth.uid())
      and ca.status = 'ativo'
      and pp.id = agp_coletas.participante_id
      and pp.projeto_id = agp_coletas.projeto_id
      and pp.funcao_no_projeto = 'atleta'
      and pp.ativo = true
      and pe.legacy_perfil_atleta_id = agp_coletas.atleta_id
      and pe.status = 'ativo'
  )
);

create policy agp_coletas_self_insert
on public.agp_coletas
for insert
to authenticated
with check (
  public.agp_is_owner()
  or (
    projeto_id is not null
    and public.agp_user_can_access_institution(public.agp_project_institution(projeto_id))
  )
  or (
    origem = 'autodeclarado'
    and coletado_por_auth_id = (select auth.uid())
    and exists (
      select 1
      from public.agp_contas_acesso ca
      join public.agp_participantes_projeto pp on pp.pessoa_id = ca.pessoa_id
      join public.agp_perfis_esportivos pe on pe.pessoa_id = ca.pessoa_id
      where ca.auth_id = (select auth.uid())
        and ca.status = 'ativo'
        and pp.id = agp_coletas.participante_id
        and pp.projeto_id = agp_coletas.projeto_id
        and pp.funcao_no_projeto = 'atleta'
        and pp.ativo = true
        and pe.legacy_perfil_atleta_id = agp_coletas.atleta_id
        and pe.status = 'ativo'
    )
  )
);

create policy agp_coletas_staff_update
on public.agp_coletas
for update
to authenticated
using (
  public.agp_is_owner()
  or (
    projeto_id is not null
    and public.agp_user_can_access_institution(public.agp_project_institution(projeto_id))
  )
)
with check (
  public.agp_is_owner()
  or (
    projeto_id is not null
    and public.agp_user_can_access_institution(public.agp_project_institution(projeto_id))
  )
);

commit;
