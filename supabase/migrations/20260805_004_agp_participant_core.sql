-- AGP-31 — Núcleo canônico de participantes
-- Projeto Supabase autorizado: kvmtfngxkeodkqrxbjwo
-- Migração aditiva. Não remove nem altera perfis_atletas ou o acesso do proprietário.

create extension if not exists pgcrypto;

create table if not exists public.agp_pessoas (
  id uuid primary key default gen_random_uuid(),
  nome text not null,
  nome_social text,
  data_nascimento date,
  email_contato text,
  telefone_contato text,
  documento_referencia text,
  status text not null default 'ativo' check (status in ('rascunho','ativo','suspenso','encerrado')),
  criado_por uuid references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists agp_pessoas_email_contato_uidx
  on public.agp_pessoas (lower(email_contato)) where email_contato is not null;

create table if not exists public.agp_contas_acesso (
  id uuid primary key default gen_random_uuid(),
  pessoa_id uuid not null references public.agp_pessoas(id) on delete cascade,
  auth_id uuid unique references auth.users(id) on delete set null,
  email_acesso text,
  status text not null default 'acesso_pendente' check (status in ('acesso_pendente','ativo','bloqueado','encerrado')),
  primeiro_acesso_em timestamptz,
  ultimo_acesso_em timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (pessoa_id)
);

create table if not exists public.agp_papeis_institucionais (
  id uuid primary key default gen_random_uuid(),
  pessoa_id uuid not null references public.agp_pessoas(id) on delete cascade,
  instituicao_id uuid not null references public.agp_instituicoes(id) on delete cascade,
  papel text not null check (papel in ('atleta','tecnico','treinador','preparador_fisico','medico','fisioterapeuta','psicologo','nutricionista','gestor','analista','responsavel_legal')),
  escopo jsonb not null default '{}'::jsonb,
  data_inicio date not null default current_date,
  data_fim date,
  status text not null default 'ativo' check (status in ('pendente','ativo','suspenso','encerrado')),
  criado_por uuid references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (pessoa_id, instituicao_id, papel)
);

create table if not exists public.agp_perfis_esportivos (
  id uuid primary key default gen_random_uuid(),
  pessoa_id uuid not null unique references public.agp_pessoas(id) on delete cascade,
  modalidade text not null,
  prova_posicao text,
  categoria text,
  idade_esportiva_anos numeric(5,2),
  nivel text,
  equipe text,
  data_ingresso date,
  status text not null default 'ativo' check (status in ('rascunho','ativo','suspenso','encerrado')),
  dados_complementares jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.agp_credenciais_profissionais (
  id uuid primary key default gen_random_uuid(),
  pessoa_id uuid not null references public.agp_pessoas(id) on delete cascade,
  profissao text not null,
  conselho text,
  numero_registro text,
  uf_registro text,
  validade date,
  status text not null default 'pendente' check (status in ('pendente','validada','vencida','suspensa')),
  documento_id uuid references public.agp_documentos_profissionais(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (pessoa_id, profissao, conselho, numero_registro)
);

create table if not exists public.agp_responsaveis_atleta (
  id uuid primary key default gen_random_uuid(),
  atleta_pessoa_id uuid not null references public.agp_pessoas(id) on delete cascade,
  responsavel_pessoa_id uuid not null references public.agp_pessoas(id) on delete cascade,
  relacao text not null,
  principal boolean not null default false,
  autorizado_responder boolean not null default false,
  data_inicio date not null default current_date,
  data_fim date,
  status text not null default 'ativo' check (status in ('ativo','suspenso','encerrado')),
  created_at timestamptz not null default now(),
  unique (atleta_pessoa_id, responsavel_pessoa_id)
);

create table if not exists public.agp_participantes_projeto (
  id uuid primary key default gen_random_uuid(),
  projeto_id uuid not null references public.agp_projetos_validacao(id) on delete cascade,
  pessoa_id uuid not null references public.agp_pessoas(id) on delete cascade,
  funcao_no_projeto text not null,
  tecnico_responsavel_pessoa_id uuid references public.agp_pessoas(id) on delete set null,
  status_onboarding text not null default 'identidade_criada' check (status_onboarding in ('rascunho','identidade_criada','acesso_pendente','perfil_pendente','vinculo_pendente','consentimento_pendente','linha_base_pendente','apto_para_coleta','ativo','suspenso','encerrado')),
  data_inicio date not null default current_date,
  data_fim date,
  ativo boolean not null default true,
  criado_por uuid references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (projeto_id, pessoa_id, funcao_no_projeto)
);

create table if not exists public.agp_auditoria_participantes (
  id bigint generated always as identity primary key,
  pessoa_id uuid references public.agp_pessoas(id) on delete set null,
  projeto_id uuid references public.agp_projetos_validacao(id) on delete set null,
  acao text not null,
  estado_anterior jsonb,
  estado_novo jsonb,
  executado_por uuid references auth.users(id),
  origem text not null default 'sistema',
  created_at timestamptz not null default now()
);

create or replace function public.agp_status_onboarding_participante(p_participante_id uuid)
returns text
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  v_participante public.agp_participantes_projeto%rowtype;
  v_tem_conta boolean;
  v_tem_perfil boolean;
  v_tem_consentimento boolean;
  v_tem_linha_base boolean;
begin
  select * into v_participante from public.agp_participantes_projeto where id = p_participante_id;
  if not found then return 'rascunho'; end if;

  select exists(select 1 from public.agp_contas_acesso where pessoa_id = v_participante.pessoa_id and status = 'ativo') into v_tem_conta;
  select exists(select 1 from public.agp_perfis_esportivos where pessoa_id = v_participante.pessoa_id and status = 'ativo') into v_tem_perfil;
  select exists(select 1 from public.agp_consentimentos c where c.atleta_id = v_participante.pessoa_id and c.concessao = true and c.revogacao is null) into v_tem_consentimento;
  select exists(select 1 from public.agp_linhas_base_atleta l where l.atleta_id = v_participante.pessoa_id) into v_tem_linha_base;

  if v_participante.funcao_no_projeto = 'atleta' then
    if not v_tem_perfil then return 'perfil_pendente'; end if;
    if not v_tem_consentimento then return 'consentimento_pendente'; end if;
    if not v_tem_linha_base then return 'linha_base_pendente'; end if;
    if not v_tem_conta then return 'acesso_pendente'; end if;
  elsif not v_tem_conta then
    return 'acesso_pendente';
  end if;

  return 'apto_para_coleta';
end;
$$;

create or replace view public.agp_participantes_elegibilidade as
select
  pp.id as participante_id,
  pp.projeto_id,
  pp.pessoa_id,
  p.nome,
  p.data_nascimento,
  pp.funcao_no_projeto,
  pp.tecnico_responsavel_pessoa_id,
  public.agp_status_onboarding_participante(pp.id) as status_calculado,
  pp.status_onboarding as status_registrado,
  pp.ativo
from public.agp_participantes_projeto pp
join public.agp_pessoas p on p.id = pp.pessoa_id;

alter table public.agp_pessoas enable row level security;
alter table public.agp_contas_acesso enable row level security;
alter table public.agp_papeis_institucionais enable row level security;
alter table public.agp_perfis_esportivos enable row level security;
alter table public.agp_credenciais_profissionais enable row level security;
alter table public.agp_responsaveis_atleta enable row level security;
alter table public.agp_participantes_projeto enable row level security;
alter table public.agp_auditoria_participantes enable row level security;

-- O proprietário mantém visão global. Membros só visualizam participantes de instituições autorizadas.
create policy agp_pessoas_owner_all on public.agp_pessoas for all
using (public.agp_is_owner()) with check (public.agp_is_owner());

create policy agp_participantes_owner_all on public.agp_participantes_projeto for all
using (public.agp_is_owner()) with check (public.agp_is_owner());

create policy agp_participantes_institution_read on public.agp_participantes_projeto for select
using (public.agp_user_can_access_institution(public.agp_project_institution_id(projeto_id)));

create policy agp_pessoas_institution_read on public.agp_pessoas for select
using (
  public.agp_is_owner() or exists (
    select 1 from public.agp_participantes_projeto pp
    where pp.pessoa_id = agp_pessoas.id
      and public.agp_user_can_access_institution(public.agp_project_institution_id(pp.projeto_id))
  )
);

create policy agp_related_owner_all_contas on public.agp_contas_acesso for all using (public.agp_is_owner()) with check (public.agp_is_owner());
create policy agp_related_owner_all_papeis on public.agp_papeis_institucionais for all using (public.agp_is_owner()) with check (public.agp_is_owner());
create policy agp_related_owner_all_perfis on public.agp_perfis_esportivos for all using (public.agp_is_owner()) with check (public.agp_is_owner());
create policy agp_related_owner_all_credenciais on public.agp_credenciais_profissionais for all using (public.agp_is_owner()) with check (public.agp_is_owner());
create policy agp_related_owner_all_responsaveis on public.agp_responsaveis_atleta for all using (public.agp_is_owner()) with check (public.agp_is_owner());
create policy agp_related_owner_all_auditoria on public.agp_auditoria_participantes for all using (public.agp_is_owner()) with check (public.agp_is_owner());

grant select on public.agp_participantes_elegibilidade to authenticated;
grant execute on function public.agp_status_onboarding_participante(uuid) to authenticated;
