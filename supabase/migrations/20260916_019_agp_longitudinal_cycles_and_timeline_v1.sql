-- AGP longitudinal temporal model v1
-- Canonical sequence: day -> microcycle -> mesocycle -> season -> career.
-- Additive, sport-agnostic core. Swimming operational entities are linked without rebuilding them.

create table if not exists public.agp_ciclos_longitudinais (
  id uuid primary key default gen_random_uuid(),
  pessoa_id uuid not null references public.agp_pessoas(id) on delete cascade,
  participante_id uuid null references public.agp_participantes_projeto(id) on delete set null,
  projeto_id uuid null references public.agp_projetos_validacao(id) on delete set null,
  perfil_especializacao_id uuid null references public.agp_perfis_especializacao_esportiva(id) on delete restrict,
  ciclo_pai_id uuid null references public.agp_ciclos_longitudinais(id) on delete restrict,
  nivel text not null check (nivel in ('dia','microciclo','mesociclo','temporada','carreira')),
  codigo text not null,
  nome text not null,
  objetivo text null,
  inicio timestamptz not null,
  fim timestamptz null,
  status text not null default 'planejado' check (status in ('planejado','ativo','concluido','cancelado')),
  contexto_planejado jsonb not null default '{}'::jsonb,
  contexto_resultante jsonb not null default '{}'::jsonb,
  criterios_sucesso jsonb not null default '[]'::jsonb,
  versao text not null default '1.0.0',
  criado_por_pessoa_id uuid null references public.agp_pessoas(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint agp_ciclos_longitudinais_periodo_check check (fim is null or fim >= inicio),
  constraint agp_ciclos_longitudinais_self_parent_check check (ciclo_pai_id is null or ciclo_pai_id <> id),
  unique (pessoa_id, codigo, versao)
);

create index if not exists agp_ciclos_longitudinais_pessoa_tempo_idx
  on public.agp_ciclos_longitudinais(pessoa_id, inicio desc);
create index if not exists agp_ciclos_longitudinais_participante_idx
  on public.agp_ciclos_longitudinais(participante_id, inicio desc);
create index if not exists agp_ciclos_longitudinais_projeto_idx
  on public.agp_ciclos_longitudinais(projeto_id, inicio desc);
create index if not exists agp_ciclos_longitudinais_pai_idx
  on public.agp_ciclos_longitudinais(ciclo_pai_id);

create table if not exists public.agp_ciclo_sessoes (
  ciclo_id uuid not null references public.agp_ciclos_longitudinais(id) on delete cascade,
  sessao_id uuid not null references public.agp_sessoes_esportivas(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (ciclo_id, sessao_id)
);

create table if not exists public.agp_ciclo_participacoes_prova (
  ciclo_id uuid not null references public.agp_ciclos_longitudinais(id) on delete cascade,
  participacao_prova_id uuid not null references public.agp_participacoes_prova(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (ciclo_id, participacao_prova_id)
);

create table if not exists public.agp_ciclo_coletas (
  ciclo_id uuid not null references public.agp_ciclos_longitudinais(id) on delete cascade,
  coleta_id uuid not null references public.agp_coletas(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (ciclo_id, coleta_id)
);

create table if not exists public.agp_ciclo_intervencoes (
  ciclo_id uuid not null references public.agp_ciclos_longitudinais(id) on delete cascade,
  intervencao_id uuid not null references public.agp_intervencoes(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (ciclo_id, intervencao_id)
);

create table if not exists public.agp_ciclo_respostas_intervencao (
  ciclo_id uuid not null references public.agp_ciclos_longitudinais(id) on delete cascade,
  resposta_intervencao_id uuid not null references public.agp_respostas_intervencao(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (ciclo_id, resposta_intervencao_id)
);

create table if not exists public.agp_marcos_longitudinais (
  id uuid primary key default gen_random_uuid(),
  pessoa_id uuid not null references public.agp_pessoas(id) on delete cascade,
  participante_id uuid null references public.agp_participantes_projeto(id) on delete set null,
  projeto_id uuid null references public.agp_projetos_validacao(id) on delete set null,
  perfil_especializacao_id uuid null references public.agp_perfis_especializacao_esportiva(id) on delete restrict,
  tipo text not null check (tipo in (
    'entrada_esporte','mudanca_categoria','mudanca_prova_funcao','mudanca_equipe','mudanca_tecnico',
    'mudanca_instituicao','inicio_temporada','fim_temporada','competicao_relevante','recorde_pessoal',
    'restricao_saude','retorno_disponibilidade','intervencao_relevante','outro'
  )),
  ocorrido_em timestamptz not null,
  titulo text not null,
  descricao text null,
  contexto jsonb not null default '{}'::jsonb,
  origem text not null default 'sistema' check (origem in ('sistema','profissional','atleta','integracao')),
  criado_por_pessoa_id uuid null references public.agp_pessoas(id) on delete set null,
  created_at timestamptz not null default now()
);

create index if not exists agp_marcos_longitudinais_pessoa_tempo_idx
  on public.agp_marcos_longitudinais(pessoa_id, ocorrido_em desc);

create or replace view public.agp_timeline_longitudinal
with (security_invoker = true)
as
select
  c.pessoa_id,
  c.participante_id,
  c.projeto_id,
  c.inicio as ocorrido_em,
  'ciclo'::text as categoria,
  c.nivel as tipo,
  c.id as referencia_id,
  c.nome as titulo,
  jsonb_build_object(
    'codigo', c.codigo,
    'status', c.status,
    'fim', c.fim,
    'objetivo', c.objetivo,
    'perfil_especializacao_id', c.perfil_especializacao_id,
    'ciclo_pai_id', c.ciclo_pai_id,
    'versao', c.versao
  ) as contexto
from public.agp_ciclos_longitudinais c
union all
select
  m.pessoa_id,
  m.participante_id,
  m.projeto_id,
  m.ocorrido_em,
  'marco'::text as categoria,
  m.tipo,
  m.id as referencia_id,
  m.titulo,
  m.contexto || jsonb_build_object(
    'descricao', m.descricao,
    'origem', m.origem,
    'perfil_especializacao_id', m.perfil_especializacao_id
  ) as contexto
from public.agp_marcos_longitudinais m;

alter table public.agp_ciclos_longitudinais enable row level security;
alter table public.agp_ciclo_sessoes enable row level security;
alter table public.agp_ciclo_participacoes_prova enable row level security;
alter table public.agp_ciclo_coletas enable row level security;
alter table public.agp_ciclo_intervencoes enable row level security;
alter table public.agp_ciclo_respostas_intervencao enable row level security;
alter table public.agp_marcos_longitudinais enable row level security;

revoke all on public.agp_timeline_longitudinal from public, anon, authenticated;
grant select on public.agp_timeline_longitudinal to service_role;
