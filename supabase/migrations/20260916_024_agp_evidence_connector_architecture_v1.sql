-- AGP evidence connector architecture v1
-- External systems are evidence sources, never alternate truth stores.
-- Raw provenance is preserved; normalized evidence must enter canonical agp_coletas.

create table if not exists public.agp_conectores_evidencia (
  id uuid primary key default gen_random_uuid(),
  codigo text not null unique,
  nome text not null,
  provedor text null,
  categoria text not null check (categoria in ('wearable','timing','biomechanics','strength_testing','health_performance_platform','manual_import','other')),
  transporte text not null check (transporte in ('api','webhook','file','manual','other')),
  capacidades jsonb not null default '{}'::jsonb,
  status text not null default 'catalogado' check (status in ('catalogado','homologacao','ativo','suspenso','descontinuado')),
  versao_conector text not null default '1.0.0',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.agp_ativacoes_conectores (
  id uuid primary key default gen_random_uuid(),
  conector_id uuid not null references public.agp_conectores_evidencia(id) on delete restrict,
  instituicao_id uuid null references public.agp_instituicoes(id) on delete cascade,
  projeto_id uuid null references public.agp_projetos_validacao(id) on delete cascade,
  participante_id uuid null references public.agp_participantes_projeto(id) on delete cascade,
  escopo_autorizado jsonb not null default '{}'::jsonb,
  status text not null default 'pendente' check (status in ('pendente','ativo','suspenso','revogado','encerrado')),
  inicio timestamptz null,
  fim timestamptz null,
  autorizado_por_pessoa_id uuid null references public.agp_pessoas(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (num_nonnulls(instituicao_id,projeto_id,participante_id) >= 1),
  check (fim is null or inicio is null or fim >= inicio)
);

create index if not exists agp_ativacoes_conectores_projeto_idx on public.agp_ativacoes_conectores(projeto_id,status);
create index if not exists agp_ativacoes_conectores_participante_idx on public.agp_ativacoes_conectores(participante_id,status);

create table if not exists public.agp_mapeamentos_conector_metrica (
  id uuid primary key default gen_random_uuid(),
  conector_id uuid not null references public.agp_conectores_evidencia(id) on delete cascade,
  metrica_id uuid not null references public.agp_metricas_esportivas_canonicas(id) on delete restrict,
  campo_externo text not null,
  unidade_externa text null,
  regra_normalizacao jsonb not null default '{}'::jsonb,
  contexto_aplicabilidade jsonb not null default '{}'::jsonb,
  status text not null default 'rascunho' check (status in ('rascunho','homologado','suspenso')),
  versao text not null default '1.0.0',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (conector_id,campo_externo,versao)
);

create table if not exists public.agp_ingestoes_externas (
  id uuid primary key default gen_random_uuid(),
  ativacao_id uuid not null references public.agp_ativacoes_conectores(id) on delete restrict,
  conector_id uuid not null references public.agp_conectores_evidencia(id) on delete restrict,
  projeto_id uuid null references public.agp_projetos_validacao(id) on delete set null,
  participante_id uuid null references public.agp_participantes_projeto(id) on delete set null,
  evento_externo_id text null,
  ocorrido_em timestamptz null,
  recebido_em timestamptz not null default now(),
  payload_bruto jsonb not null,
  metadados_origem jsonb not null default '{}'::jsonb,
  hash_integridade text null,
  status text not null default 'recebido' check (status in ('recebido','normalizado','parcial','rejeitado','duplicado')),
  motivo_status text null,
  created_at timestamptz not null default now()
);

create unique index if not exists agp_ingestoes_externas_evento_unique
  on public.agp_ingestoes_externas(conector_id,evento_externo_id)
  where evento_externo_id is not null;
create index if not exists agp_ingestoes_externas_participante_tempo_idx
  on public.agp_ingestoes_externas(participante_id,coalesce(ocorrido_em,recebido_em) desc);

create table if not exists public.agp_ingestao_coletas (
  ingestao_id uuid not null references public.agp_ingestoes_externas(id) on delete cascade,
  coleta_id uuid not null references public.agp_coletas(id) on delete cascade,
  papel text not null default 'normalizada' check (papel in ('normalizada','complementar','correcao')),
  created_at timestamptz not null default now(),
  primary key (ingestao_id,coleta_id)
);

alter table public.agp_conectores_evidencia enable row level security;
alter table public.agp_ativacoes_conectores enable row level security;
alter table public.agp_mapeamentos_conector_metrica enable row level security;
alter table public.agp_ingestoes_externas enable row level security;
alter table public.agp_ingestao_coletas enable row level security;

revoke all on public.agp_conectores_evidencia from public,anon,authenticated;
revoke all on public.agp_ativacoes_conectores from public,anon,authenticated;
revoke all on public.agp_mapeamentos_conector_metrica from public,anon,authenticated;
revoke all on public.agp_ingestoes_externas from public,anon,authenticated;
revoke all on public.agp_ingestao_coletas from public,anon,authenticated;

grant select,insert,update,delete on public.agp_conectores_evidencia to service_role;
grant select,insert,update,delete on public.agp_ativacoes_conectores to service_role;
grant select,insert,update,delete on public.agp_mapeamentos_conector_metrica to service_role;
grant select,insert,update,delete on public.agp_ingestoes_externas to service_role;
grant select,insert,update,delete on public.agp_ingestao_coletas to service_role;

comment on table public.agp_ingestoes_externas is
'Immutable-source ingestion envelope preserving external provenance. Scientific/operational interpretation occurs only after normalization into canonical AGP collections.';
comment on table public.agp_mapeamentos_conector_metrica is
'Versioned mapping from external fields to canonical AGP metrics. Device/vendor fields do not become canonical metrics by themselves.';
