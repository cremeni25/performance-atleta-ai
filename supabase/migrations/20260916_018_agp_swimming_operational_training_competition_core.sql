-- AGP Swimming operational core: training + competition + evidence linkage
-- This migration materializes the next canonical layer after identity/roles/competence.
-- It does NOT introduce final UI and does NOT duplicate the evidence architecture.
-- Operational entities are linked back to agp_coletas, protocols and canonical metrics.

create table if not exists public.agp_sessoes_esportivas (
  id uuid primary key default gen_random_uuid(),
  projeto_id uuid not null references public.agp_projetos_validacao(id) on delete cascade,
  participante_id uuid not null references public.agp_participantes_projeto(id) on delete cascade,
  perfil_especializacao_id uuid not null references public.agp_perfis_especializacao_esportiva(id) on delete restrict,
  tipo_sessao text not null check (tipo_sessao in ('pool_training','dry_land','recovery','assessment','other')),
  status text not null default 'planejada' check (status in ('planejada','em_execucao','concluida','cancelada')),
  objetivo text null,
  inicio_planejado timestamptz null,
  fim_planejado timestamptz null,
  inicio_real timestamptz null,
  fim_real timestamptz null,
  contexto_esportivo jsonb not null default '{}'::jsonb,
  planejado_por_pessoa_id uuid null references public.agp_pessoas(id) on delete set null,
  registrado_por_pessoa_id uuid null references public.agp_pessoas(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists agp_sessoes_esportivas_participante_data_idx
  on public.agp_sessoes_esportivas(participante_id, coalesce(inicio_real,inicio_planejado));
create index if not exists agp_sessoes_esportivas_projeto_idx
  on public.agp_sessoes_esportivas(projeto_id);

create table if not exists public.agp_unidades_sessao (
  id uuid primary key default gen_random_uuid(),
  sessao_id uuid not null references public.agp_sessoes_esportivas(id) on delete cascade,
  parent_id uuid null references public.agp_unidades_sessao(id) on delete cascade,
  nivel text not null check (nivel in ('block','set','repetition','segment')),
  ordem integer not null check (ordem >= 0),
  nome text null,
  objetivo text null,
  planejado jsonb not null default '{}'::jsonb,
  executado jsonb not null default '{}'::jsonb,
  status text not null default 'planejada' check (status in ('planejada','parcial','executada','omitida','cancelada')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (sessao_id, parent_id, ordem)
);

create index if not exists agp_unidades_sessao_parent_idx on public.agp_unidades_sessao(parent_id);
create index if not exists agp_unidades_sessao_sessao_idx on public.agp_unidades_sessao(sessao_id,nivel,ordem);

create table if not exists public.agp_competicoes (
  id uuid primary key default gen_random_uuid(),
  projeto_id uuid not null references public.agp_projetos_validacao(id) on delete cascade,
  perfil_especializacao_id uuid not null references public.agp_perfis_especializacao_esportiva(id) on delete restrict,
  nome text not null,
  organizador text null,
  local text null,
  inicio date not null,
  fim date null,
  status text not null default 'planejada' check (status in ('planejada','em_andamento','concluida','cancelada')),
  contexto_competitivo jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (fim is null or fim >= inicio)
);

create index if not exists agp_competicoes_projeto_data_idx on public.agp_competicoes(projeto_id,inicio);

create table if not exists public.agp_provas_competicao (
  id uuid primary key default gen_random_uuid(),
  competicao_id uuid not null references public.agp_competicoes(id) on delete cascade,
  codigo_evento text null,
  estilo text not null,
  distancia_m numeric not null check (distancia_m > 0),
  piscina_m numeric not null check (piscina_m in (25,50)),
  etapa text null,
  bateria text null,
  horario_previsto timestamptz null,
  contexto_prova jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists agp_provas_competicao_competicao_idx on public.agp_provas_competicao(competicao_id);

create table if not exists public.agp_participacoes_prova (
  id uuid primary key default gen_random_uuid(),
  prova_id uuid not null references public.agp_provas_competicao(id) on delete cascade,
  participante_id uuid not null references public.agp_participantes_projeto(id) on delete cascade,
  raia integer null check (raia is null or raia >= 0),
  status text not null default 'inscrito' check (status in ('inscrito','confirmado','realizado','dns','dnf','dsq','cancelado')),
  tempo_oficial_ms bigint null check (tempo_oficial_ms is null or tempo_oficial_ms >= 0),
  classificacao integer null check (classificacao is null or classificacao > 0),
  codigo_desclassificacao text null,
  fonte_resultado jsonb not null default '{}'::jsonb,
  contexto_resultado jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (prova_id, participante_id)
);

create index if not exists agp_participacoes_prova_participante_idx
  on public.agp_participacoes_prova(participante_id);

create table if not exists public.agp_segmentos_prova (
  id uuid primary key default gen_random_uuid(),
  participacao_id uuid not null references public.agp_participacoes_prova(id) on delete cascade,
  ordem integer not null check (ordem >= 0),
  tipo_segmento text not null check (tipo_segmento in ('start','split','turn','underwater','overwater','finish','transition','other')),
  inicio_m numeric null,
  fim_m numeric null,
  tempo_ms bigint null check (tempo_ms is null or tempo_ms >= 0),
  dados_segmento jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (participacao_id, ordem, tipo_segmento),
  check (inicio_m is null or inicio_m >= 0),
  check (fim_m is null or fim_m >= 0),
  check (inicio_m is null or fim_m is null or fim_m >= inicio_m)
);

create index if not exists agp_segmentos_prova_participacao_idx
  on public.agp_segmentos_prova(participacao_id,ordem);

-- Metric-level values remain inside the canonical evidence envelope (agp_coletas).
-- This prevents a parallel evidence system and lets new metrics be catalog/configuration rather than DDL.
create table if not exists public.agp_coleta_metricas (
  id uuid primary key default gen_random_uuid(),
  coleta_id uuid not null references public.agp_coletas(id) on delete cascade,
  metrica_id uuid not null references public.agp_metricas_esportivas_canonicas(id) on delete restrict,
  metrica_versao_id uuid null references public.agp_metrica_versoes(id) on delete restrict,
  ordem integer not null default 0 check (ordem >= 0),
  valor_numerico numeric null,
  valor_texto text null,
  valor_json jsonb null,
  unidade text null,
  contexto_medicao jsonb not null default '{}'::jsonb,
  qualidade jsonb not null default '{}'::jsonb,
  measured_at timestamptz null,
  created_at timestamptz not null default now(),
  check (num_nonnulls(valor_numerico,valor_texto,valor_json) >= 1)
);

create index if not exists agp_coleta_metricas_coleta_idx on public.agp_coleta_metricas(coleta_id);
create index if not exists agp_coleta_metricas_metrica_idx on public.agp_coleta_metricas(metrica_id,measured_at);

create table if not exists public.agp_vinculos_evidencia_operacional (
  coleta_id uuid primary key references public.agp_coletas(id) on delete cascade,
  sessao_id uuid null references public.agp_sessoes_esportivas(id) on delete cascade,
  unidade_sessao_id uuid null references public.agp_unidades_sessao(id) on delete cascade,
  participacao_prova_id uuid null references public.agp_participacoes_prova(id) on delete cascade,
  segmento_prova_id uuid null references public.agp_segmentos_prova(id) on delete cascade,
  created_at timestamptz not null default now(),
  check (num_nonnulls(sessao_id,unidade_sessao_id,participacao_prova_id,segmento_prova_id) = 1)
);

-- Backend-governed by default. Final role RLS policies will be attached after operational service rules are closed.
alter table public.agp_sessoes_esportivas enable row level security;
alter table public.agp_unidades_sessao enable row level security;
alter table public.agp_competicoes enable row level security;
alter table public.agp_provas_competicao enable row level security;
alter table public.agp_participacoes_prova enable row level security;
alter table public.agp_segmentos_prova enable row level security;
alter table public.agp_coleta_metricas enable row level security;
alter table public.agp_vinculos_evidencia_operacional enable row level security;

revoke all on public.agp_sessoes_esportivas from public, anon, authenticated;
revoke all on public.agp_unidades_sessao from public, anon, authenticated;
revoke all on public.agp_competicoes from public, anon, authenticated;
revoke all on public.agp_provas_competicao from public, anon, authenticated;
revoke all on public.agp_participacoes_prova from public, anon, authenticated;
revoke all on public.agp_segmentos_prova from public, anon, authenticated;
revoke all on public.agp_coleta_metricas from public, anon, authenticated;
revoke all on public.agp_vinculos_evidencia_operacional from public, anon, authenticated;

grant select,insert,update,delete on public.agp_sessoes_esportivas to service_role;
grant select,insert,update,delete on public.agp_unidades_sessao to service_role;
grant select,insert,update,delete on public.agp_competicoes to service_role;
grant select,insert,update,delete on public.agp_provas_competicao to service_role;
grant select,insert,update,delete on public.agp_participacoes_prova to service_role;
grant select,insert,update,delete on public.agp_segmentos_prova to service_role;
grant select,insert,update,delete on public.agp_coleta_metricas to service_role;
grant select,insert,update,delete on public.agp_vinculos_evidencia_operacional to service_role;

comment on table public.agp_sessoes_esportivas is
'Canonical sport-session envelope. Swimming uses pool_training and dry_land now; future sports may extend through Sport Domain Profiles without changing identity/evidence core.';
comment on table public.agp_unidades_sessao is
'Hierarchical session structure (block/set/repetition/segment). Sport-specific planned/executed semantics live in JSON while quantitative evidence stays in canonical metric collections.';
comment on table public.agp_coleta_metricas is
'Metric-level values inside the existing AGP evidence envelope; canonical metrics remain catalog-driven and versionable.';
