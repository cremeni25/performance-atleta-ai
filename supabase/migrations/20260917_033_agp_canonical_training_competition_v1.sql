-- AGP canonical training + competition lifecycle v1
-- Preserve legacy data while moving the operational center to person/participant/project/cycle.

alter table public.agp_sessoes_treinamento
  add column if not exists pessoa_id uuid null references public.agp_pessoas(id) on delete restrict,
  add column if not exists participante_id uuid null references public.agp_participantes_projeto(id) on delete set null,
  add column if not exists projeto_id uuid null references public.agp_projetos_validacao(id) on delete set null,
  add column if not exists ciclo_id uuid null references public.agp_ciclos_longitudinais(id) on delete set null,
  add column if not exists perfil_especializacao_id uuid null references public.agp_perfis_especializacao_esportiva(id) on delete set null,
  add column if not exists origem_registro text not null default 'manual';

alter table public.agp_sessoes_treinamento alter column atleta_id drop not null;

alter table public.agp_sessoes_treinamento
  drop constraint if exists agp_sessoes_treinamento_identidade_check;
alter table public.agp_sessoes_treinamento
  add constraint agp_sessoes_treinamento_identidade_check
  check (pessoa_id is not null or atleta_id is not null) not valid;
alter table public.agp_sessoes_treinamento validate constraint agp_sessoes_treinamento_identidade_check;

update public.agp_sessoes_treinamento s
set pessoa_id = pe.pessoa_id,
    participante_id = coalesce(s.participante_id, pp.id),
    projeto_id = coalesce(s.projeto_id, pp.projeto_id)
from public.agp_perfis_esportivos pe
left join public.agp_participantes_projeto pp
  on pp.pessoa_id = pe.pessoa_id and pp.ativo = true
where s.pessoa_id is null
  and s.atleta_id is not null
  and pe.legacy_perfil_atleta_id = s.atleta_id;

create index if not exists agp_sessoes_treinamento_pessoa_data_idx
  on public.agp_sessoes_treinamento(pessoa_id, data_hora_inicio desc);
create index if not exists agp_sessoes_treinamento_participante_data_idx
  on public.agp_sessoes_treinamento(participante_id, data_hora_inicio desc);
create index if not exists agp_sessoes_treinamento_ciclo_idx
  on public.agp_sessoes_treinamento(ciclo_id);

create or replace view public.agp_sessoes_treinamento_canonicas
with (security_invoker = true)
as
select
  s.id,
  coalesce(s.pessoa_id, pe.pessoa_id) as pessoa_id,
  coalesce(s.participante_id, pp.id) as participante_id,
  coalesce(s.projeto_id, pp.projeto_id) as projeto_id,
  s.ciclo_id,
  s.perfil_especializacao_id,
  s.plano_id,
  s.tecnico_auth_id,
  s.data_hora_inicio,
  s.duracao_min,
  s.volume_planejado,
  s.volume_executado,
  s.intensidade_planejada,
  s.intensidade_percebida,
  s.carga_interna,
  s.carga_externa,
  s.conteudo,
  s.intercorrencias,
  s.origem_registro,
  s.created_at,
  case when s.pessoa_id is not null then 'canonico' else 'ponte_legado' end as origem_identidade
from public.agp_sessoes_treinamento s
left join public.agp_perfis_esportivos pe on pe.legacy_perfil_atleta_id = s.atleta_id
left join public.agp_participantes_projeto pp
  on pp.pessoa_id = coalesce(s.pessoa_id, pe.pessoa_id)
  and (s.projeto_id is null or pp.projeto_id = s.projeto_id)
  and pp.ativo = true;

create table if not exists public.agp_participacoes_competicao (
  id uuid primary key default gen_random_uuid(),
  pessoa_id uuid not null references public.agp_pessoas(id) on delete restrict,
  participante_id uuid not null references public.agp_participantes_projeto(id) on delete restrict,
  projeto_id uuid not null references public.agp_projetos_validacao(id) on delete restrict,
  ciclo_id uuid null references public.agp_ciclos_longitudinais(id) on delete set null,
  competicao_id uuid not null references public.agp_competicoes(id) on delete cascade,
  prova_id uuid not null references public.agp_provas_competicao(id) on delete cascade,
  status text not null default 'planejada' check (status in ('planejada','inscrita','confirmada','disputada','dns','dnf','dsq','cancelada')),
  raia text null,
  tempo_inscricao_ms bigint null check (tempo_inscricao_ms is null or tempo_inscricao_ms >= 0),
  tempo_oficial_ms bigint null check (tempo_oficial_ms is null or tempo_oficial_ms >= 0),
  colocacao_serie integer null check (colocacao_serie is null or colocacao_serie > 0),
  colocacao_geral integer null check (colocacao_geral is null or colocacao_geral > 0),
  pontos numeric null,
  resultado_contexto jsonb not null default '{}'::jsonb,
  fonte_resultado text null,
  confirmado_por_pessoa_id uuid null references public.agp_pessoas(id) on delete set null,
  confirmado_em timestamptz null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (participante_id, prova_id)
);

create table if not exists public.agp_parciais_competicao (
  id uuid primary key default gen_random_uuid(),
  participacao_id uuid not null references public.agp_participacoes_competicao(id) on delete cascade,
  distancia_acumulada_m numeric not null check (distancia_acumulada_m > 0),
  tempo_acumulado_ms bigint not null check (tempo_acumulado_ms >= 0),
  tempo_parcial_ms bigint null check (tempo_parcial_ms is null or tempo_parcial_ms >= 0),
  origem text not null default 'oficial',
  qualidade text not null default 'nao_avaliada' check (qualidade in ('nao_avaliada','confirmada','estimada','revisao_requerida')),
  contexto jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (participacao_id, distancia_acumulada_m)
);

create index if not exists agp_participacoes_competicao_pessoa_idx
  on public.agp_participacoes_competicao(pessoa_id, created_at desc);
create index if not exists agp_participacoes_competicao_projeto_idx
  on public.agp_participacoes_competicao(projeto_id, competicao_id);
create index if not exists agp_participacoes_competicao_ciclo_idx
  on public.agp_participacoes_competicao(ciclo_id);
create index if not exists agp_parciais_competicao_participacao_idx
  on public.agp_parciais_competicao(participacao_id, distancia_acumulada_m);

alter table public.agp_participacoes_competicao enable row level security;
alter table public.agp_parciais_competicao enable row level security;

revoke all on public.agp_sessoes_treinamento_canonicas from public, anon, authenticated;
revoke all on public.agp_participacoes_competicao from public, anon, authenticated;
revoke all on public.agp_parciais_competicao from public, anon, authenticated;
grant select on public.agp_sessoes_treinamento_canonicas to service_role;
grant select, insert, update, delete on public.agp_participacoes_competicao to service_role;
grant select, insert, update, delete on public.agp_parciais_competicao to service_role;

comment on view public.agp_sessoes_treinamento_canonicas is 'Canonical training projection centered on person/participant/project/cycle while preserving legacy sessions.';
comment on table public.agp_participacoes_competicao is 'Athlete competition participation/result fact. No result semantics beyond recorded facts without separate scientific/professional interpretation.';
comment on table public.agp_parciais_competicao is 'Swimming competition split facts linked to a canonical participation.';