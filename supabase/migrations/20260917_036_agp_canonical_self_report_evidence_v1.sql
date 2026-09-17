-- Canonical self-report / evidence identity for Point Zero.
-- Preserves legacy athlete_id only as a compatibility bridge.

alter table public.agp_coletas
  add column if not exists pessoa_id uuid null references public.agp_pessoas(id) on delete restrict,
  add column if not exists natureza_validacao text not null default 'nao_aplicavel'
    check (natureza_validacao in ('nao_aplicavel','autoria_estrutura','profissional','sistema'));

update public.agp_coletas c
set pessoa_id = pp.pessoa_id
from public.agp_participantes_projeto pp
where c.pessoa_id is null
  and c.participante_id = pp.id;

update public.agp_coletas c
set pessoa_id = pe.pessoa_id
from public.agp_perfis_esportivos pe
where c.pessoa_id is null
  and c.atleta_id is not null
  and pe.legacy_perfil_atleta_id = c.atleta_id;

alter table public.agp_coletas alter column atleta_id drop not null;

alter table public.agp_coletas drop constraint if exists agp_coletas_identidade_canonica_check;
alter table public.agp_coletas add constraint agp_coletas_identidade_canonica_check
  check (pessoa_id is not null or atleta_id is not null) not valid;
alter table public.agp_coletas validate constraint agp_coletas_identidade_canonica_check;

create index if not exists agp_coletas_pessoa_data_idx
  on public.agp_coletas(pessoa_id, data_hora_coleta desc);

create or replace view public.agp_coletas_canonicas
with (security_invoker = true)
as
select
  c.id,
  coalesce(c.pessoa_id, pp.pessoa_id, pe.pessoa_id) as pessoa_id,
  c.participante_id,
  c.atleta_id,
  c.projeto_id,
  c.instrumento_id,
  c.ativacao_instrumento_id,
  i.codigo as instrumento_codigo,
  i.nome as instrumento_nome,
  i.respondente,
  c.protocolo_id,
  c.coletado_por_auth_id,
  c.papel_coletor,
  c.data_hora_coleta,
  c.data_hora_registro,
  c.origem,
  c.status,
  c.completude,
  c.confiabilidade,
  c.dados,
  c.natureza_validacao,
  c.validado_por_auth_id,
  c.validado_em,
  c.versao_instrumento,
  c.versao_schema,
  c.ciclo_referencia,
  c.janela_inicio,
  c.janela_fim,
  c.iniciado_em,
  c.submetido_em,
  c.bloqueado_para_edicao,
  c.liberado_motor_em,
  c.hash_resposta,
  c.created_at,
  c.updated_at,
  case when c.pessoa_id is not null then 'canonico' else 'ponte_legado' end as origem_identidade
from public.agp_coletas c
left join public.agp_participantes_projeto pp on pp.id = c.participante_id
left join public.agp_perfis_esportivos pe on pe.legacy_perfil_atleta_id = c.atleta_id
left join public.agp_instrumentos i on i.id = c.instrumento_id;

revoke all on public.agp_coletas_canonicas from public, anon, authenticated;
grant select on public.agp_coletas_canonicas to service_role;

comment on column public.agp_coletas.natureza_validacao is
  'Meaning of validation status. autoria_estrutura validates authorship/schema of self-report, not clinical truth.';
comment on view public.agp_coletas_canonicas is
  'Canonical evidence projection centered on person/participant; legacy athlete id is compatibility only.';
