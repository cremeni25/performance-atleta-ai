-- AGP Swimming - persistent professional training workspace drafts
-- One draft per professional + project. Service-role backend is the only writer.

create table if not exists public.agp_rascunhos_treino (
  id uuid primary key default gen_random_uuid(),
  projeto_id uuid not null references public.agp_projetos_validacao(id) on delete cascade,
  pessoa_id uuid not null references public.agp_pessoas(id) on delete cascade,
  payload jsonb not null default '{}'::jsonb,
  versao integer not null default 1,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (projeto_id, pessoa_id)
);

create index if not exists agp_rascunhos_treino_projeto_idx
  on public.agp_rascunhos_treino(projeto_id);

create index if not exists agp_rascunhos_treino_pessoa_idx
  on public.agp_rascunhos_treino(pessoa_id);

alter table public.agp_rascunhos_treino enable row level security;
revoke all on public.agp_rascunhos_treino from public, anon, authenticated;
grant select, insert, update, delete on public.agp_rascunhos_treino to service_role;

comment on table public.agp_rascunhos_treino is
'Persistent professional training workspace draft. Preserves unsaved training planning and execution input across page reload, tab/application switching and browser suspension.';
