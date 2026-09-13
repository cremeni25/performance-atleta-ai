begin;

alter table public.agp_respostas_intervencao
  add column if not exists visivel_atleta boolean not null default false,
  add column if not exists visivel_comissao boolean not null default true,
  add column if not exists visivel_instituicao boolean not null default false;

drop policy if exists agp_respostas_intervencao_atleta_select on public.agp_respostas_intervencao;
create policy agp_respostas_intervencao_atleta_select on public.agp_respostas_intervencao
for select using (
  visivel_atleta is true
  and exists (
    select 1
    from public.agp_contas_acesso conta
    join public.agp_perfis_esportivos perfil on perfil.pessoa_id = conta.pessoa_id
    where conta.auth_id = auth.uid()
      and conta.status = 'ativo'
      and perfil.status = 'ativo'
      and perfil.legacy_perfil_atleta_id = agp_respostas_intervencao.atleta_id
  )
);

grant select on public.agp_respostas_intervencao to authenticated;

commit;
