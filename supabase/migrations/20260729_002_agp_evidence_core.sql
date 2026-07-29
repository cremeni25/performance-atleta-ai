begin;

create extension if not exists pgcrypto;

create table if not exists public.agp_protocolos (
  id uuid primary key default gen_random_uuid(),
  instituicao_id uuid references public.agp_instituicoes(id) on delete cascade,
  nome text not null,
  dominio text not null check (dominio in ('fisico','fisiologico','biologico','tecnico','mental','psicologico','medico','recuperacao','contextual','crescimento','maturacao','coletivo')),
  modalidade text,
  categoria text,
  versao text not null,
  objetivo text not null,
  criterios jsonb not null default '{}'::jsonb,
  limites_interpretacao text,
  ativo boolean not null default true,
  criado_por uuid,
  revisado_por uuid,
  data_revisao timestamptz,
  created_at timestamptz not null default now(),
  unique (instituicao_id, nome, versao)
);

create table if not exists public.agp_fontes_cientificas (
  id uuid primary key default gen_random_uuid(),
  titulo text not null,
  autores text,
  organizacao text,
  ano integer,
  tipo text not null check (tipo in ('artigo','consenso','diretriz','livro','protocolo','norma','base_dados')),
  doi text,
  url text,
  resumo text,
  nivel_evidencia text,
  status_validacao text not null default 'pendente' check (status_validacao in ('pendente','validada','rejeitada','obsoleta')),
  validado_por uuid,
  validado_em timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists public.agp_protocolo_fontes (
  protocolo_id uuid not null references public.agp_protocolos(id) on delete cascade,
  fonte_id uuid not null references public.agp_fontes_cientificas(id) on delete cascade,
  justificativa text,
  primary key (protocolo_id, fonte_id)
);

create table if not exists public.agp_instrumentos (
  id uuid primary key default gen_random_uuid(),
  protocolo_id uuid references public.agp_protocolos(id) on delete restrict,
  nome text not null,
  versao text not null,
  tipo text not null check (tipo in ('questionario','teste','escala','observacao','dispositivo','laboratorio','avaliacao_profissional','registro_competitivo')),
  respondente text not null check (respondente in ('atleta','tecnico','medico','fisioterapeuta','psicologo','preparador_fisico','nutricionista','gestor','dispositivo','laboratorio')),
  periodicidade text,
  schema_campos jsonb not null default '{}'::jsonb,
  regra_completude jsonb not null default '{}'::jsonb,
  ativo boolean not null default true,
  created_at timestamptz not null default now(),
  unique (nome, versao)
);

create table if not exists public.agp_linhas_base_atleta (
  id uuid primary key default gen_random_uuid(),
  atleta_id uuid not null references public.perfis_atletas(id) on delete cascade,
  projeto_id uuid references public.agp_projetos_validacao(id) on delete set null,
  categoria text,
  idade_cronologica numeric(5,2),
  sexo_registrado text,
  modalidade text,
  prova_posicao text,
  estagio_maturacional text,
  altura_cm numeric(6,2),
  massa_kg numeric(6,2),
  envergadura_cm numeric(6,2),
  data_referencia date not null,
  origem text not null,
  responsavel_auth_id uuid,
  observacoes text,
  created_at timestamptz not null default now()
);

create table if not exists public.agp_coletas (
  id uuid primary key default gen_random_uuid(),
  atleta_id uuid not null references public.perfis_atletas(id) on delete cascade,
  projeto_id uuid references public.agp_projetos_validacao(id) on delete set null,
  instrumento_id uuid not null references public.agp_instrumentos(id) on delete restrict,
  protocolo_id uuid references public.agp_protocolos(id) on delete restrict,
  coletado_por_auth_id uuid,
  papel_coletor text not null,
  data_hora_coleta timestamptz not null,
  data_hora_registro timestamptz not null default now(),
  origem text not null check (origem in ('autodeclarado','observacao_profissional','dispositivo','laboratorio','importacao','competicao')),
  status text not null default 'rascunho' check (status in ('rascunho','completa','validada','rejeitada','corrigida')),
  completude numeric(5,2) not null default 0 check (completude between 0 and 100),
  confiabilidade numeric(5,2) check (confiabilidade between 0 and 100),
  dados jsonb not null default '{}'::jsonb,
  justificativa_correcao text,
  validado_por_auth_id uuid,
  validado_em timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists public.agp_planos_tecnicos (
  id uuid primary key default gen_random_uuid(),
  atleta_id uuid references public.perfis_atletas(id) on delete cascade,
  projeto_id uuid references public.agp_projetos_validacao(id) on delete cascade,
  tecnico_auth_id uuid not null,
  nome text not null,
  objetivo text not null,
  hipotese text,
  metodologia text not null,
  criterios_sucesso jsonb not null default '{}'::jsonb,
  periodo_inicio date not null,
  periodo_fim date,
  versao text not null,
  status text not null default 'planejado' check (status in ('planejado','em_execucao','pausado','concluido','cancelado')),
  created_at timestamptz not null default now()
);

create table if not exists public.agp_sessoes_treinamento (
  id uuid primary key default gen_random_uuid(),
  plano_id uuid references public.agp_planos_tecnicos(id) on delete set null,
  atleta_id uuid not null references public.perfis_atletas(id) on delete cascade,
  tecnico_auth_id uuid,
  data_hora_inicio timestamptz not null,
  duracao_min integer,
  volume_planejado numeric,
  volume_executado numeric,
  intensidade_planejada numeric,
  intensidade_percebida numeric,
  carga_interna numeric,
  carga_externa numeric,
  conteudo jsonb not null default '{}'::jsonb,
  intercorrencias text,
  created_at timestamptz not null default now()
);

create table if not exists public.agp_intervencoes (
  id uuid primary key default gen_random_uuid(),
  atleta_id uuid not null references public.perfis_atletas(id) on delete cascade,
  projeto_id uuid references public.agp_projetos_validacao(id) on delete set null,
  plano_id uuid references public.agp_planos_tecnicos(id) on delete set null,
  dominio text not null,
  responsavel_auth_id uuid not null,
  papel_responsavel text not null,
  descricao text not null,
  justificativa text not null,
  evidencia_origem jsonb not null default '[]'::jsonb,
  resultado_esperado jsonb not null default '{}'::jsonb,
  inicio timestamptz not null,
  fim_previsto timestamptz,
  status text not null default 'proposta' check (status in ('proposta','aprovada','em_execucao','concluida','cancelada')),
  created_at timestamptz not null default now()
);

create table if not exists public.agp_resultados_analiticos (
  id uuid primary key default gen_random_uuid(),
  atleta_id uuid not null references public.perfis_atletas(id) on delete cascade,
  projeto_id uuid references public.agp_projetos_validacao(id) on delete set null,
  tipo text not null check (tipo in ('score_dimensional','score_global','tendencia','alerta','comparacao_metodo','previsao','relatorio')),
  versao_motor text not null,
  protocolo_id uuid references public.agp_protocolos(id) on delete restrict,
  janela_inicio timestamptz,
  janela_fim timestamptz,
  entradas jsonb not null default '[]'::jsonb,
  resultado jsonb not null,
  explicacao text not null,
  confianca numeric(5,2) check (confianca between 0 and 100),
  limitacoes text,
  status text not null default 'preliminar' check (status in ('preliminar','validado','rejeitado','substituido')),
  validado_por_auth_id uuid,
  validado_em timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists public.agp_documentos_profissionais (
  id uuid primary key default gen_random_uuid(),
  atleta_id uuid not null references public.perfis_atletas(id) on delete cascade,
  projeto_id uuid references public.agp_projetos_validacao(id) on delete set null,
  tipo text not null check (tipo in ('avaliacao_medica','laudo','liberacao','restricao','avaliacao_fisioterapica','avaliacao_psicologica','avaliacao_nutricional','avaliacao_tecnica')),
  profissional_auth_id uuid,
  conselho_registro text,
  data_documento date not null,
  validade_ate date,
  resumo text not null,
  restricoes jsonb not null default '[]'::jsonb,
  arquivo_ref text,
  status text not null default 'vigente' check (status in ('vigente','vencido','revogado','substituido')),
  created_at timestamptz not null default now()
);

create table if not exists public.agp_consentimentos (
  id uuid primary key default gen_random_uuid(),
  atleta_id uuid not null references public.perfis_atletas(id) on delete cascade,
  responsavel_legal_auth_id uuid,
  finalidade text not null,
  versao_termo text not null,
  concedido_em timestamptz not null,
  revogado_em timestamptz,
  escopo jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_agp_coletas_atleta_data on public.agp_coletas(atleta_id, data_hora_coleta desc);
create index if not exists idx_agp_sessoes_atleta_data on public.agp_sessoes_treinamento(atleta_id, data_hora_inicio desc);
create index if not exists idx_agp_resultados_atleta_data on public.agp_resultados_analiticos(atleta_id, created_at desc);
create index if not exists idx_agp_intervencoes_atleta_data on public.agp_intervencoes(atleta_id, inicio desc);
create index if not exists idx_agp_documentos_atleta_data on public.agp_documentos_profissionais(atleta_id, data_documento desc);

alter table public.agp_protocolos enable row level security;
alter table public.agp_fontes_cientificas enable row level security;
alter table public.agp_protocolo_fontes enable row level security;
alter table public.agp_instrumentos enable row level security;
alter table public.agp_linhas_base_atleta enable row level security;
alter table public.agp_coletas enable row level security;
alter table public.agp_planos_tecnicos enable row level security;
alter table public.agp_sessoes_treinamento enable row level security;
alter table public.agp_intervencoes enable row level security;
alter table public.agp_resultados_analiticos enable row level security;
alter table public.agp_documentos_profissionais enable row level security;
alter table public.agp_consentimentos enable row level security;

commit;
