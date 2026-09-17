begin;

-- Canonical professional assessment: person-centered, multi-role and competence-aware.
-- Legacy atleta_id is preserved only as an optional compatibility bridge.

alter table public.agp_avaliacoes_profissionais
  add column if not exists pessoa_id uuid references public.agp_pessoas(id) on delete cascade,
  add column if not exists ciclo_id uuid references public.agp_ciclos_longitudinais(id) on delete set null,
  add column if not exists competencia_codigo text references public.agp_competencias_canonicas(codigo) on delete restrict,
  add column if not exists credencial_verificada_no_registro boolean not null default false,
  add column if not exists natureza_avaliacao text not null default 'profissional',
  add column if not exists evidencia_referencia jsonb not null default '[]'::jsonb;

update public.agp_avaliacoes_profissionais a
set pessoa_id = pp.pessoa_id
from public.agp_participantes_projeto pp
where a.participante_id = pp.id
  and a.pessoa_id is null;

alter table public.agp_avaliacoes_profissionais
  alter column atleta_id drop not null;

alter table public.agp_avaliacoes_profissionais
  add constraint agp_avaliacoes_profissionais_pessoa_required_chk
  check (pessoa_id is not null) not valid;

alter table public.agp_avaliacoes_profissionais
  validate constraint agp_avaliacoes_profissionais_pessoa_required_chk;

create index if not exists agp_avaliacoes_profissionais_pessoa_data_idx
  on public.agp_avaliacoes_profissionais(pessoa_id, data_avaliacao desc);
create index if not exists agp_avaliacoes_profissionais_participante_dominio_idx
  on public.agp_avaliacoes_profissionais(participante_id, dominio, data_avaliacao desc);

create or replace view public.agp_avaliacoes_profissionais_canonicas
with (security_invoker = true)
as
select
  a.id,
  a.pessoa_id,
  a.participante_id,
  a.projeto_id,
  a.ciclo_id,
  a.atleta_id as legacy_atleta_id,
  a.dominio,
  a.papel_profissional,
  a.competencia_codigo,
  a.credencial_verificada_no_registro,
  a.natureza_avaliacao,
  a.profissional_auth_id,
  a.data_avaliacao,
  a.validade_ate,
  a.instrumento_referencia,
  a.metricas,
  a.achados,
  a.restricoes,
  a.recomendacoes,
  a.evidencia_referencia,
  a.confianca,
  a.status,
  a.created_at,
  a.updated_at
from public.agp_avaliacoes_profissionais a;

revoke all on public.agp_avaliacoes_profissionais_canonicas from public, anon, authenticated;
grant select on public.agp_avaliacoes_profissionais_canonicas to service_role;

comment on column public.agp_avaliacoes_profissionais.competencia_codigo is
  'Canonical competence exercised for this assessment. Regulated domains require verified credential at write time.';
comment on column public.agp_avaliacoes_profissionais.credencial_verificada_no_registro is
  'Immutable operational snapshot indicating whether the required professional credential was verified when the assessment was recorded.';
comment on column public.agp_avaliacoes_profissionais.atleta_id is
  'LEGACY compatibility bridge only. Canonical identity is pessoa_id + participante_id + projeto_id.';

commit;
