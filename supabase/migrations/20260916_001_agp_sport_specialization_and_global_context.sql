-- AGP canonical sport specialization + global context
-- Purpose: provide one AGP Core with sport-specific intelligence and locale-aware presentation.
-- This migration is intentionally additive. It does not remove or rewrite legacy esporte/modalidade structures.

create extension if not exists pgcrypto;

create table if not exists public.agp_esportes_canonicos (
  id uuid primary key default gen_random_uuid(),
  codigo text not null unique,
  nome_canonico text not null,
  natureza text not null check (natureza in ('individual','coletivo','misto')),
  contato text not null default 'variavel' check (contato in ('contato','nao_contato','variavel')),
  legado_esporte_id uuid null references public.esportes(id) on delete set null,
  ativo boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.agp_modalidades_canonicas (
  id uuid primary key default gen_random_uuid(),
  esporte_id uuid not null references public.agp_esportes_canonicos(id) on delete cascade,
  codigo text not null,
  nome_canonico text not null,
  tipo_ambiente text null,
  estrutura_competitiva jsonb not null default '{}'::jsonb,
  legado_modalidade_id uuid null references public.modalidades(id) on delete set null,
  ativo boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (esporte_id, codigo)
);

create table if not exists public.agp_perfis_especializacao_esportiva (
  id uuid primary key default gen_random_uuid(),
  esporte_id uuid not null references public.agp_esportes_canonicos(id) on delete cascade,
  modalidade_id uuid null references public.agp_modalidades_canonicas(id) on delete cascade,
  codigo text not null,
  versao text not null,
  status_catalogo text not null default 'rascunho' check (status_catalogo in ('rascunho','aprovado','desativado')),
  ontologia jsonb not null default '{}'::jsonb,
  estrutura_treino jsonb not null default '{}'::jsonb,
  estrutura_competitiva jsonb not null default '{}'::jsonb,
  estrutura_papeis jsonb not null default '{}'::jsonb,
  categorias jsonb not null default '[]'::jsonb,
  posicoes_provas_funcoes jsonb not null default '[]'::jsonb,
  dominios_prioritarios jsonb not null default '[]'::jsonb,
  modelo_carga_recuperacao jsonb not null default '{}'::jsonb,
  modelo_desenvolvimento jsonb not null default '{}'::jsonb,
  regras_contextuais jsonb not null default '{}'::jsonb,
  integracoes_recomendadas jsonb not null default '[]'::jsonb,
  metadados jsonb not null default '{}'::jsonb,
  aprovado_por uuid null references auth.users(id) on delete set null,
  aprovado_em timestamptz null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (codigo, versao)
);

create table if not exists public.agp_locales (
  codigo text primary key,
  idioma text not null,
  pais_codigo char(2) null,
  locale_fallback text null references public.agp_locales(codigo) on delete set null,
  sistema_unidades text not null default 'metric' check (sistema_unidades in ('metric','imperial','mixed')),
  timezone_padrao text null,
  formatos jsonb not null default '{}'::jsonb,
  ativo boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.agp_lexico_esportivo (
  id uuid primary key default gen_random_uuid(),
  conceito_chave text not null,
  locale_codigo text not null references public.agp_locales(codigo) on delete cascade,
  esporte_id uuid null references public.agp_esportes_canonicos(id) on delete cascade,
  modalidade_id uuid null references public.agp_modalidades_canonicas(id) on delete cascade,
  termo text not null,
  termo_curto text null,
  sinonimos jsonb not null default '[]'::jsonb,
  contexto_uso text null,
  observacoes jsonb not null default '{}'::jsonb,
  ativo boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (conceito_chave, locale_codigo, esporte_id, modalidade_id)
);

create table if not exists public.agp_contextos_globais_projeto (
  projeto_id uuid primary key references public.agp_projetos_validacao(id) on delete cascade,
  perfil_especializacao_id uuid not null references public.agp_perfis_especializacao_esportiva(id) on delete restrict,
  locale_codigo text not null references public.agp_locales(codigo) on delete restrict,
  pais_codigo char(2) null,
  timezone text null,
  sistema_unidades text null check (sistema_unidades is null or sistema_unidades in ('metric','imperial','mixed')),
  configuracao_local jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists agp_modalidades_canonicas_esporte_idx
  on public.agp_modalidades_canonicas(esporte_id);

create index if not exists agp_perfis_especializacao_esportiva_lookup_idx
  on public.agp_perfis_especializacao_esportiva(esporte_id, modalidade_id, status_catalogo);

create index if not exists agp_lexico_esportivo_lookup_idx
  on public.agp_lexico_esportivo(locale_codigo, esporte_id, modalidade_id, conceito_chave);

alter table public.agp_esportes_canonicos enable row level security;
alter table public.agp_modalidades_canonicas enable row level security;
alter table public.agp_perfis_especializacao_esportiva enable row level security;
alter table public.agp_locales enable row level security;
alter table public.agp_lexico_esportivo enable row level security;
alter table public.agp_contextos_globais_projeto enable row level security;

comment on table public.agp_esportes_canonicos is 'Canonical sport identity for AGP Core. Distinct from legacy esporte registration.';
comment on table public.agp_modalidades_canonicas is 'Canonical sport modality/subdomain used by sport specialization profiles.';
comment on table public.agp_perfis_especializacao_esportiva is 'Versioned sport intelligence package: ontology, training, competition, roles, metrics context and development model.';
comment on table public.agp_locales is 'Semantic locale configuration; not simple string translation.';
comment on table public.agp_lexico_esportivo is 'Locale- and sport-aware terminology mapped to canonical AGP concepts.';
comment on table public.agp_contextos_globais_projeto is 'Binds each project to one approved sport specialization and one locale context.';

-- Deliberately no authenticated/anon policies here.
-- Until access rules are implemented, these tables remain service-role / backend governed.
