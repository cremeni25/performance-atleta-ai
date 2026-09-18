-- AGP Swimming — team/group training planning with individualization.
-- Prescription is organizational context; each athlete receives a canonical session in agp_sessoes_esportivas.

create table if not exists public.agp_grupos_treinamento (
  id uuid primary key default gen_random_uuid(),
  projeto_id uuid not null references public.agp_projetos_validacao(id) on delete cascade,
  perfil_especializacao_id uuid not null references public.agp_perfis_especializacao_esportiva(id) on delete restrict,
  nome text not null,
  descricao text null,
  ativo boolean not null default true,
  criado_por_pessoa_id uuid null references public.agp_pessoas(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (projeto_id,nome)
);

create table if not exists public.agp_grupo_treinamento_participantes (
  grupo_id uuid not null references public.agp_grupos_treinamento(id) on delete cascade,
  participante_id uuid not null references public.agp_participantes_projeto(id) on delete cascade,
  ativo boolean not null default true,
  data_inicio date not null default current_date,
  data_fim date null,
  created_at timestamptz not null default now(),
  primary key (grupo_id,participante_id),
  check (data_fim is null or data_fim >= data_inicio)
);

create table if not exists public.agp_planos_treino (
  id uuid primary key default gen_random_uuid(),
  projeto_id uuid not null references public.agp_projetos_validacao(id) on delete cascade,
  perfil_especializacao_id uuid not null references public.agp_perfis_especializacao_esportiva(id) on delete restrict,
  grupo_id uuid null references public.agp_grupos_treinamento(id) on delete set null,
  tipo_sessao text not null check (tipo_sessao in ('pool_training','dry_land','recovery','assessment','other')),
  status text not null default 'planejado' check (status in ('rascunho','planejado','em_execucao','concluido','cancelado')),
  objetivo text null,
  inicio_planejado timestamptz not null,
  duracao_min integer null check (duracao_min is null or (duracao_min >= 1 and duracao_min <= 600)),
  prescricao_base jsonb not null default '{}'::jsonb,
  criado_por_pessoa_id uuid null references public.agp_pessoas(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.agp_plano_treino_atletas (
  plano_id uuid not null references public.agp_planos_treino(id) on delete cascade,
  participante_id uuid not null references public.agp_participantes_projeto(id) on delete cascade,
  origem text not null check (origem in ('grupo','individual')),
  ajustes_individuais jsonb not null default '{}'::jsonb,
  sessao_id uuid null unique references public.agp_sessoes_esportivas(id) on delete set null,
  created_at timestamptz not null default now(),
  primary key (plano_id,participante_id)
);

create index if not exists agp_grupos_treinamento_projeto_idx on public.agp_grupos_treinamento(projeto_id,ativo);
create index if not exists agp_grupo_treinamento_participantes_participante_idx on public.agp_grupo_treinamento_participantes(participante_id,ativo);
create index if not exists agp_planos_treino_projeto_data_idx on public.agp_planos_treino(projeto_id,inicio_planejado desc);
create index if not exists agp_plano_treino_atletas_participante_idx on public.agp_plano_treino_atletas(participante_id);

alter table public.agp_grupos_treinamento enable row level security;
alter table public.agp_grupo_treinamento_participantes enable row level security;
alter table public.agp_planos_treino enable row level security;
alter table public.agp_plano_treino_atletas enable row level security;

revoke all on public.agp_grupos_treinamento from public,anon,authenticated;
revoke all on public.agp_grupo_treinamento_participantes from public,anon,authenticated;
revoke all on public.agp_planos_treino from public,anon,authenticated;
revoke all on public.agp_plano_treino_atletas from public,anon,authenticated;

grant select,insert,update,delete on public.agp_grupos_treinamento to service_role;
grant select,insert,update,delete on public.agp_grupo_treinamento_participantes to service_role;
grant select,insert,update,delete on public.agp_planos_treino to service_role;
grant select,insert,update,delete on public.agp_plano_treino_atletas to service_role;

comment on table public.agp_grupos_treinamento is
'Operational training groups inside a project. Groups organize prescription; they do not replace the athlete as the longitudinal center.';
comment on table public.agp_planos_treino is
'Team/group or individual training prescription envelope. Materialized athlete sessions remain the canonical operational fact in agp_sessoes_esportivas.';
comment on table public.agp_plano_treino_atletas is
'Recipients of a training plan with optional individual adjustments and link to each athlete canonical session.';
