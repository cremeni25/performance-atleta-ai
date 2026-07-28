-- AGP: núcleo multi-institucional para homologação e pilotos técnicos
create extension if not exists pgcrypto;

create table if not exists public.agp_instituicoes (
  id uuid primary key default gen_random_uuid(),
  nome text not null,
  slug text not null unique,
  tipo text not null default 'homologacao' check (tipo in ('homologacao','clube','associacao','instituto','academia')),
  localidade text,
  status text not null default 'ativo' check (status in ('ativo','suspenso','encerrado')),
  criado_por uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.agp_membros_instituicao (
  id uuid primary key default gen_random_uuid(),
  instituicao_id uuid not null references public.agp_instituicoes(id) on delete cascade,
  auth_id uuid not null,
  nome text,
  email text,
  papel text not null check (papel in ('admin_institucional','tecnico','assistente','atleta','observador')),
  acesso_total_tecnico boolean not null default false,
  ativo boolean not null default true,
  inicio_acesso timestamptz not null default now(),
  fim_acesso timestamptz,
  created_at timestamptz not null default now(),
  unique (instituicao_id, auth_id)
);

create table if not exists public.agp_projetos_validacao (
  id uuid primary key default gen_random_uuid(),
  instituicao_id uuid not null references public.agp_instituicoes(id) on delete cascade,
  nome text not null,
  objetivo text not null,
  metodologia text,
  diretrizes text,
  localidade text,
  data_inicio date,
  data_fim date,
  status text not null default 'preparacao' check (status in ('preparacao','homologacao','em_campo','concluido','suspenso')),
  versao_motor text not null default 'agp-core-v2',
  created_at timestamptz not null default now()
);

create table if not exists public.agp_atletas_projeto (
  id uuid primary key default gen_random_uuid(),
  projeto_id uuid not null references public.agp_projetos_validacao(id) on delete cascade,
  atleta_id uuid not null,
  tecnico_responsavel_auth_id uuid,
  status text not null default 'ativo' check (status in ('ativo','pausado','concluido','retirado')),
  data_entrada date not null default current_date,
  data_saida date,
  created_at timestamptz not null default now(),
  unique (projeto_id, atleta_id)
);

create table if not exists public.agp_eventos_auditoria (
  id bigint generated always as identity primary key,
  instituicao_id uuid references public.agp_instituicoes(id) on delete set null,
  projeto_id uuid references public.agp_projetos_validacao(id) on delete set null,
  auth_id uuid,
  papel text,
  evento text not null,
  entidade text,
  entidade_id text,
  detalhes jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_agp_membros_auth on public.agp_membros_instituicao(auth_id);
create index if not exists idx_agp_projetos_instituicao on public.agp_projetos_validacao(instituicao_id);
create index if not exists idx_agp_atletas_projeto on public.agp_atletas_projeto(projeto_id, atleta_id);
create index if not exists idx_agp_auditoria_instituicao on public.agp_eventos_auditoria(instituicao_id, created_at desc);

alter table public.agp_instituicoes enable row level security;
alter table public.agp_membros_instituicao enable row level security;
alter table public.agp_projetos_validacao enable row level security;
alter table public.agp_atletas_projeto enable row level security;
alter table public.agp_eventos_auditoria enable row level security;

create or replace function public.agp_is_owner()
returns boolean
language sql stable security definer set search_path = public
as $$
  select coalesce((auth.jwt() -> 'user_metadata' ->> 'is_owner')::boolean, false)
      or lower(coalesce(auth.jwt() ->> 'email','')) = 'anderson@cremeni.com.br';
$$;

create or replace function public.agp_has_institution_access(target uuid)
returns boolean
language sql stable security definer set search_path = public
as $$
  select public.agp_is_owner() or exists (
    select 1 from public.agp_membros_instituicao m
    where m.instituicao_id = target
      and m.auth_id = auth.uid()
      and m.ativo = true
      and (m.fim_acesso is null or m.fim_acesso > now())
  );
$$;

drop policy if exists agp_instituicoes_select on public.agp_instituicoes;
create policy agp_instituicoes_select on public.agp_instituicoes for select using (public.agp_has_institution_access(id));

drop policy if exists agp_membros_select on public.agp_membros_instituicao;
create policy agp_membros_select on public.agp_membros_instituicao for select using (public.agp_has_institution_access(instituicao_id));

drop policy if exists agp_projetos_select on public.agp_projetos_validacao;
create policy agp_projetos_select on public.agp_projetos_validacao for select using (public.agp_has_institution_access(instituicao_id));

drop policy if exists agp_atletas_select on public.agp_atletas_projeto;
create policy agp_atletas_select on public.agp_atletas_projeto for select using (
  exists (select 1 from public.agp_projetos_validacao p where p.id = projeto_id and public.agp_has_institution_access(p.instituicao_id))
);

drop policy if exists agp_auditoria_select on public.agp_eventos_auditoria;
create policy agp_auditoria_select on public.agp_eventos_auditoria for select using (public.agp_has_institution_access(instituicao_id));

-- Escrita: proprietário ou administrador institucional.
create or replace function public.agp_can_manage_institution(target uuid)
returns boolean
language sql stable security definer set search_path = public
as $$
  select public.agp_is_owner() or exists (
    select 1 from public.agp_membros_instituicao m
    where m.instituicao_id = target
      and m.auth_id = auth.uid()
      and m.papel = 'admin_institucional'
      and m.ativo = true
  );
$$;

create policy agp_instituicoes_owner_write on public.agp_instituicoes for all using (public.agp_is_owner()) with check (public.agp_is_owner());
create policy agp_membros_manage on public.agp_membros_instituicao for all using (public.agp_can_manage_institution(instituicao_id)) with check (public.agp_can_manage_institution(instituicao_id));
create policy agp_projetos_manage on public.agp_projetos_validacao for all using (public.agp_can_manage_institution(instituicao_id)) with check (public.agp_can_manage_institution(instituicao_id));
create policy agp_atletas_manage on public.agp_atletas_projeto for all using (
  exists (select 1 from public.agp_projetos_validacao p where p.id = projeto_id and public.agp_can_manage_institution(p.instituicao_id))
) with check (
  exists (select 1 from public.agp_projetos_validacao p where p.id = projeto_id and public.agp_can_manage_institution(p.instituicao_id))
);
create policy agp_auditoria_insert on public.agp_eventos_auditoria for insert with check (public.agp_has_institution_access(instituicao_id));
