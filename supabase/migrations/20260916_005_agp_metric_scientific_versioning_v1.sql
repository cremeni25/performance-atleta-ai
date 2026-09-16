-- AGP metric scientific versioning V1
-- Mirrors production migration 20260916160040.
-- Additive. No public/authenticated policies are created.

create extension if not exists pgcrypto;

create table if not exists public.agp_metrica_versoes (
  id uuid primary key default gen_random_uuid(),
  metrica_id uuid not null references public.agp_metricas_esportivas_canonicas(id) on delete cascade,
  versao text not null,
  conceito_canonico text not null,
  definicao_cientifica text not null,
  tipo_semantico text not null check (tipo_semantico in ('bruto','derivado','bruto_derivado','interpretacao')),
  formula_descritiva text null,
  protocolo_minimo jsonb not null default '{}'::jsonb,
  aplicabilidade jsonb not null default '{}'::jsonb,
  qualidade_evidencia jsonb not null default '{}'::jsonb,
  responsavel_primario text null,
  periodicidade text null,
  equipamento_necessario text null,
  limitacoes text null,
  calculo_automatico text null,
  obrigatoriedade text not null default 'contextual',
  observacao_canonica text null,
  status_catalogo text not null default 'rascunho'
    check (status_catalogo in ('rascunho','validacao','aprovado','obsoleto')),
  vigente_desde timestamptz not null default now(),
  vigente_ate timestamptz null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (metrica_id, versao)
);

create table if not exists public.agp_metrica_aliases (
  alias_codigo text primary key,
  metrica_canonica_id uuid not null references public.agp_metricas_esportivas_canonicas(id) on delete restrict,
  origem text not null default 'legado',
  observacao text null,
  ativo boolean not null default true,
  created_at timestamptz not null default now()
);

create index if not exists idx_agp_metrica_versoes_metrica
  on public.agp_metrica_versoes(metrica_id);
create index if not exists idx_agp_metrica_versoes_status
  on public.agp_metrica_versoes(status_catalogo);
create index if not exists idx_agp_metrica_aliases_canonica
  on public.agp_metrica_aliases(metrica_canonica_id);

alter table public.agp_metrica_versoes enable row level security;
alter table public.agp_metrica_aliases enable row level security;

comment on table public.agp_metrica_versoes is
  'Versioned scientific semantics for canonical sport metrics. Formula/protocol revisions create a new version instead of overwriting history.';
comment on table public.agp_metrica_aliases is
  'Explicit compatibility aliases from legacy metric codes to scientifically compatible canonical metrics. Ambiguous legacy concepts must not be aliased.';
