begin;

-- AGP-37 — Catálogo institucional de protocolos e instrumentos
-- Aplicar exclusivamente no projeto AGP: kvmtfngxkeodkqrxbjwo

alter table public.agp_protocolos
  add column if not exists codigo text,
  add column if not exists status_catalogo text not null default 'rascunho'
    check (status_catalogo in ('rascunho','em_revisao','aprovado','suspenso','obsoleto')),
  add column if not exists aprovado_por uuid references auth.users(id),
  add column if not exists aprovado_em timestamptz,
  add column if not exists updated_at timestamptz not null default now();

create unique index if not exists agp_protocolos_codigo_versao_uidx
  on public.agp_protocolos (coalesce(instituicao_id, '00000000-0000-0000-0000-000000000000'::uuid), codigo, versao)
  where codigo is not null;

alter table public.agp_instrumentos
  add column if not exists codigo text,
  add column if not exists descricao text,
  add column if not exists status_catalogo text not null default 'rascunho'
    check (status_catalogo in ('rascunho','em_revisao','aprovado','suspenso','obsoleto')),
  add column if not exists aprovado_por uuid references auth.users(id),
  add column if not exists aprovado_em timestamptz,
  add column if not exists updated_at timestamptz not null default now();

create unique index if not exists agp_instrumentos_codigo_versao_uidx
  on public.agp_instrumentos (codigo, versao)
  where codigo is not null;

create table if not exists public.agp_ativacoes_instrumentos (
  id uuid primary key default gen_random_uuid(),
  instrumento_id uuid not null references public.agp_instrumentos(id) on delete cascade,
  instituicao_id uuid references public.agp_instituicoes(id) on delete cascade,
  projeto_id uuid references public.agp_projetos_validacao(id) on delete cascade,
  modalidade text,
  categoria text,
  versao_configuracao text not null default '1.0.0',
  obrigatorio boolean not null default true,
  ordem integer not null default 0,
  periodicidade_override text,
  configuracao jsonb not null default '{}'::jsonb,
  data_inicio date not null default current_date,
  data_fim date,
  ativo boolean not null default true,
  criado_por uuid references auth.users(id),
  aprovado_por uuid references auth.users(id),
  aprovado_em timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (instituicao_id is not null or projeto_id is not null),
  check (data_fim is null or data_fim >= data_inicio)
);

create unique index if not exists agp_ativacoes_instrumentos_escopo_uidx
on public.agp_ativacoes_instrumentos (
  instrumento_id,
  coalesce(projeto_id, '00000000-0000-0000-0000-000000000000'::uuid),
  coalesce(instituicao_id, '00000000-0000-0000-0000-000000000000'::uuid),
  coalesce(lower(modalidade), ''),
  coalesce(lower(categoria), ''),
  versao_configuracao
);

alter table public.agp_ativacoes_instrumentos enable row level security;
create policy agp_ativacoes_owner_all on public.agp_ativacoes_instrumentos for all
  using (public.agp_is_owner()) with check (public.agp_is_owner());
create policy agp_ativacoes_institution_read on public.agp_ativacoes_instrumentos for select
  using (
    public.agp_is_owner()
    or (projeto_id is not null and public.agp_user_can_access_institution(public.agp_project_institution_id(projeto_id)))
    or (instituicao_id is not null and public.agp_user_can_access_institution(instituicao_id))
  );

create or replace function public.agp_instrumentos_ativos_disponiveis(
  p_projeto_id uuid,
  p_modalidade text default null,
  p_categoria text default null
)
returns integer
language sql
stable
security definer
set search_path = public
as $$
  select count(distinct i.id)::integer
  from public.agp_instrumentos i
  join public.agp_protocolos p on p.id = i.protocolo_id
  join public.agp_ativacoes_instrumentos a on a.instrumento_id = i.id
  where i.ativo = true
    and i.status_catalogo = 'aprovado'
    and p.ativo = true
    and p.status_catalogo = 'aprovado'
    and a.ativo = true
    and current_date >= a.data_inicio
    and (a.data_fim is null or current_date <= a.data_fim)
    and (a.projeto_id = p_projeto_id or (a.projeto_id is null and a.instituicao_id = public.agp_project_institution_id(p_projeto_id)))
    and (a.modalidade is null or p_modalidade is null or lower(a.modalidade) = lower(p_modalidade))
    and (a.categoria is null or p_categoria is null or lower(a.categoria) = lower(p_categoria));
$$;

create or replace view public.agp_catalogo_instrumentos_operacional as
select
  a.id as ativacao_id,
  a.instituicao_id,
  a.projeto_id,
  a.modalidade,
  a.categoria,
  a.versao_configuracao,
  a.obrigatorio,
  a.ordem,
  a.periodicidade_override,
  a.configuracao,
  a.data_inicio,
  a.data_fim,
  a.ativo as ativacao_ativa,
  p.id as protocolo_id,
  p.codigo as protocolo_codigo,
  p.nome as protocolo_nome,
  p.dominio,
  p.versao as protocolo_versao,
  p.status_catalogo as protocolo_status,
  i.id as instrumento_id,
  i.codigo as instrumento_codigo,
  i.nome as instrumento_nome,
  i.tipo,
  i.respondente,
  i.versao as instrumento_versao,
  i.status_catalogo as instrumento_status,
  i.schema_campos,
  i.regra_completude
from public.agp_ativacoes_instrumentos a
join public.agp_instrumentos i on i.id = a.instrumento_id
join public.agp_protocolos p on p.id = i.protocolo_id;

grant select on public.agp_catalogo_instrumentos_operacional to authenticated;
grant execute on function public.agp_instrumentos_ativos_disponiveis(uuid,text,text) to authenticated;

commit;
