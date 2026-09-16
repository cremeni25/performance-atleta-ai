-- AGP integrative AI governance v1
-- AI is an interpretation layer over authorized canonical evidence, never a source of truth.
-- This schema stores model/prompt/source lineage and blocks silent untraceable outputs.

create table if not exists public.agp_modelos_ia_governados (
  codigo text primary key,
  provedor text not null,
  modelo text not null,
  finalidade text not null,
  politica jsonb not null default '{}'::jsonb,
  status text not null default 'rascunho' check (status in ('rascunho','homologacao','ativo','suspenso','descontinuado')),
  versao_configuracao text not null default '1.0.0',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.agp_prompts_ia_versionados (
  id uuid primary key default gen_random_uuid(),
  codigo text not null,
  versao text not null,
  finalidade text not null,
  template text not null,
  regras_saida jsonb not null default '{}'::jsonb,
  status text not null default 'rascunho' check (status in ('rascunho','homologacao','ativo','suspenso','descontinuado')),
  created_at timestamptz not null default now(),
  unique (codigo,versao)
);

create table if not exists public.agp_execucoes_ia_integrativa (
  id uuid primary key default gen_random_uuid(),
  pessoa_id uuid null references public.agp_pessoas(id) on delete set null,
  participante_id uuid null references public.agp_participantes_projeto(id) on delete set null,
  projeto_id uuid null references public.agp_projetos_validacao(id) on delete set null,
  instituicao_id uuid null references public.agp_instituicoes(id) on delete set null,
  ciclo_id uuid null references public.agp_ciclos_longitudinais(id) on delete set null,
  solicitado_por_pessoa_id uuid not null references public.agp_pessoas(id) on delete restrict,
  papel_solicitante text null,
  finalidade text not null,
  modelo_codigo text null references public.agp_modelos_ia_governados(codigo) on delete restrict,
  prompt_id uuid null references public.agp_prompts_ia_versionados(id) on delete restrict,
  estado text not null default 'preparacao' check (estado in ('preparacao','dados_insuficientes','pronta_execucao','executada','revisao_profissional','validada','rejeitada','erro')),
  tipo_saida text null check (tipo_saida is null or tipo_saida in ('fato','inferencia','hipotese','suporte_decisao')),
  entrada_contexto jsonb not null default '{}'::jsonb,
  saida_estruturada jsonb null,
  explicacao text null,
  confianca numeric null check (confianca is null or (confianca >= 0 and confianca <= 1)),
  limitacoes text null,
  exige_validacao_profissional boolean not null default false,
  dominio_validacao text null,
  executado_em timestamptz null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (num_nonnulls(pessoa_id,participante_id,projeto_id,instituicao_id) >= 1)
);

create index if not exists agp_execucoes_ia_participante_idx on public.agp_execucoes_ia_integrativa(participante_id,created_at desc);
create index if not exists agp_execucoes_ia_projeto_idx on public.agp_execucoes_ia_integrativa(projeto_id,created_at desc);

create table if not exists public.agp_execucao_ia_evidencias (
  execucao_id uuid not null references public.agp_execucoes_ia_integrativa(id) on delete cascade,
  tipo_evidencia text not null check (tipo_evidencia in ('coleta','metrica_observada','serie_longitudinal','sessao','competicao','intervencao','resposta_intervencao','marco','interpretacao_validada','contexto')),
  referencia_id uuid null,
  referencia_codigo text null,
  resumo jsonb not null default '{}'::jsonb,
  autorizada boolean not null default true,
  created_at timestamptz not null default now(),
  primary key (execucao_id,tipo_evidencia,referencia_id,referencia_codigo),
  check (referencia_id is not null or referencia_codigo is not null)
);

create table if not exists public.agp_execucao_ia_fontes_cientificas (
  execucao_id uuid not null references public.agp_execucoes_ia_integrativa(id) on delete cascade,
  fonte_id uuid not null references public.agp_fontes_cientificas(id) on delete restrict,
  uso text not null check (uso in ('definicao','metodo','interpretacao','limitacao','contexto')),
  created_at timestamptz not null default now(),
  primary key (execucao_id,fonte_id,uso)
);

create table if not exists public.agp_validacoes_execucao_ia (
  id uuid primary key default gen_random_uuid(),
  execucao_id uuid not null references public.agp_execucoes_ia_integrativa(id) on delete cascade,
  validador_pessoa_id uuid not null references public.agp_pessoas(id) on delete restrict,
  papel_codigo text null references public.agp_papeis_canonicos(codigo) on delete restrict,
  competencia_codigo text null references public.agp_competencias_canonicas(codigo) on delete restrict,
  decisao text not null check (decisao in ('validada','revisao','rejeitada')),
  parecer text null,
  created_at timestamptz not null default now()
);

alter table public.agp_modelos_ia_governados enable row level security;
alter table public.agp_prompts_ia_versionados enable row level security;
alter table public.agp_execucoes_ia_integrativa enable row level security;
alter table public.agp_execucao_ia_evidencias enable row level security;
alter table public.agp_execucao_ia_fontes_cientificas enable row level security;
alter table public.agp_validacoes_execucao_ia enable row level security;

revoke all on public.agp_modelos_ia_governados from public,anon,authenticated;
revoke all on public.agp_prompts_ia_versionados from public,anon,authenticated;
revoke all on public.agp_execucoes_ia_integrativa from public,anon,authenticated;
revoke all on public.agp_execucao_ia_evidencias from public,anon,authenticated;
revoke all on public.agp_execucao_ia_fontes_cientificas from public,anon,authenticated;
revoke all on public.agp_validacoes_execucao_ia from public,anon,authenticated;

grant select,insert,update,delete on public.agp_modelos_ia_governados to service_role;
grant select,insert,update,delete on public.agp_prompts_ia_versionados to service_role;
grant select,insert,update,delete on public.agp_execucoes_ia_integrativa to service_role;
grant select,insert,update,delete on public.agp_execucao_ia_evidencias to service_role;
grant select,insert,update,delete on public.agp_execucao_ia_fontes_cientificas to service_role;
grant select,insert,update,delete on public.agp_validacoes_execucao_ia to service_role;

comment on table public.agp_execucoes_ia_integrativa is
'Governed integrative-AI execution ledger. Every output must retain authorized input lineage, model/prompt version, confidence, limitations and professional-validation requirement.';
comment on table public.agp_execucao_ia_evidencias is
'Canonical evidence lineage used by an AI execution. Absence of adequate authorized evidence must lead to dados_insuficientes rather than invented interpretation.';
