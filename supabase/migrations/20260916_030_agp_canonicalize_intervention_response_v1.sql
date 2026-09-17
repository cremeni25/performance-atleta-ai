-- Canonicalize intervention/response without destroying legacy data.
-- New writes may use pessoa/participante identity without requiring the legacy athlete profile.

alter table public.agp_intervencoes add column if not exists pessoa_id uuid null references public.agp_pessoas(id) on delete restrict;
alter table public.agp_intervencoes add column if not exists participante_id uuid null references public.agp_participantes_projeto(id) on delete set null;
alter table public.agp_intervencoes add column if not exists ciclo_id uuid null references public.agp_ciclos_longitudinais(id) on delete set null;
alter table public.agp_intervencoes add column if not exists decisao_id uuid null references public.agp_decisoes_canonicas(id) on delete set null;
alter table public.agp_intervencoes alter column atleta_id drop not null;
alter table public.agp_intervencoes add constraint agp_intervencoes_identidade_check
  check (pessoa_id is not null or atleta_id is not null) not valid;
alter table public.agp_intervencoes validate constraint agp_intervencoes_identidade_check;

alter table public.agp_respostas_intervencao add column if not exists pessoa_id uuid null references public.agp_pessoas(id) on delete restrict;
alter table public.agp_respostas_intervencao add column if not exists ciclo_id uuid null references public.agp_ciclos_longitudinais(id) on delete set null;
alter table public.agp_respostas_intervencao add column if not exists estado_comparabilidade text not null default 'nao_avaliado'
  check (estado_comparabilidade in ('nao_avaliado','comparavel','dados_insuficientes','nao_comparavel','revisao_requerida'));
alter table public.agp_respostas_intervencao add column if not exists classificacao_profissional text null
  check (classificacao_profissional is null or classificacao_profissional in ('favoravel','neutra','desfavoravel','inconclusiva'));
alter table public.agp_respostas_intervencao add column if not exists significado_automatico text not null default 'mudanca_observada_sem_julgamento';
alter table public.agp_respostas_intervencao alter column atleta_id drop not null;

update public.agp_intervencoes i
set pessoa_id = (
      select pe.pessoa_id
      from public.agp_perfis_esportivos pe
      where pe.legacy_perfil_atleta_id=i.atleta_id and pe.status='ativo'
      limit 1
    )
where i.pessoa_id is null and i.atleta_id is not null;

update public.agp_intervencoes i
set participante_id = (
      select pp.id
      from public.agp_participantes_projeto pp
      where pp.pessoa_id=i.pessoa_id
        and (i.projeto_id is null or pp.projeto_id=i.projeto_id)
        and pp.ativo=true
      order by pp.data_inicio desc nulls last
      limit 1
    )
where i.participante_id is null and i.pessoa_id is not null;

update public.agp_respostas_intervencao r
set pessoa_id = pp.pessoa_id
from public.agp_participantes_projeto pp
where r.pessoa_id is null and r.participante_id=pp.id;

create index if not exists agp_intervencoes_pessoa_idx on public.agp_intervencoes(pessoa_id,inicio desc);
create index if not exists agp_respostas_intervencao_pessoa_idx on public.agp_respostas_intervencao(pessoa_id,data_avaliacao desc);

create or replace view public.agp_intervencoes_canonicas
with (security_invoker = true)
as
select
  i.id,
  coalesce(i.pessoa_id, pe.pessoa_id) as pessoa_id,
  coalesce(i.participante_id, pp.id) as participante_id,
  i.projeto_id,i.ciclo_id,i.decisao_id,i.dominio,i.responsavel_auth_id,i.papel_responsavel,
  i.descricao,i.justificativa,i.evidencia_origem,i.resultado_esperado,i.inicio,i.fim_previsto,i.status,i.created_at,
  case when i.pessoa_id is not null then 'canonico' else 'ponte_legado' end as origem_identidade
from public.agp_intervencoes i
left join public.agp_perfis_esportivos pe on pe.legacy_perfil_atleta_id=i.atleta_id
left join public.agp_participantes_projeto pp on pp.pessoa_id=coalesce(i.pessoa_id,pe.pessoa_id)
  and (i.projeto_id is null or pp.projeto_id=i.projeto_id) and pp.ativo=true;

revoke all on public.agp_intervencoes_canonicas from public,anon,authenticated;
grant select on public.agp_intervencoes_canonicas to service_role;

comment on column public.agp_respostas_intervencao.classificacao_profissional is 'Optional human interpretation. Automatic processing must not manufacture favorable/unfavorable judgment.';
comment on column public.agp_respostas_intervencao.estado_comparabilidade is 'Whether before/after evidence is sufficiently equivalent for interpretation.';
comment on view public.agp_intervencoes_canonicas is 'Canonical intervention projection centered on person/participant while preserving legacy records.';