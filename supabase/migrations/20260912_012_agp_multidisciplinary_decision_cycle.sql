begin;

create table if not exists public.agp_avaliacoes_profissionais (
  id uuid primary key default gen_random_uuid(),
  participante_id uuid not null references public.agp_participantes_projeto(id) on delete cascade,
  atleta_id uuid not null references public.perfis_atletas(id) on delete cascade,
  projeto_id uuid not null references public.agp_projetos_validacao(id) on delete cascade,
  dominio text not null check (dominio in ('fisico','fisiologico','biologico','tecnico','mental','psicologico','medico','recuperacao','contextual','crescimento','maturacao','nutricional')),
  papel_profissional text not null,
  profissional_auth_id uuid not null references auth.users(id),
  data_avaliacao timestamptz not null default now(),
  validade_ate timestamptz,
  instrumento_referencia text,
  metricas jsonb not null default '{}'::jsonb,
  achados jsonb not null default '[]'::jsonb,
  restricoes jsonb not null default '[]'::jsonb,
  recomendacoes jsonb not null default '[]'::jsonb,
  confianca numeric check (confianca is null or (confianca >= 0 and confianca <= 100)),
  status text not null default 'validada' check (status in ('rascunho','validada','substituida','cancelada')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_agp_avaliacoes_prof_participante_data on public.agp_avaliacoes_profissionais(participante_id, data_avaliacao desc);
create index if not exists idx_agp_avaliacoes_prof_atleta_dominio on public.agp_avaliacoes_profissionais(atleta_id, dominio, data_avaliacao desc);

create table if not exists public.agp_respostas_intervencao (
  id uuid primary key default gen_random_uuid(),
  intervencao_id uuid not null references public.agp_intervencoes(id) on delete cascade,
  participante_id uuid not null references public.agp_participantes_projeto(id) on delete cascade,
  atleta_id uuid not null references public.perfis_atletas(id) on delete cascade,
  projeto_id uuid not null references public.agp_projetos_validacao(id) on delete cascade,
  avaliado_por_auth_id uuid not null references auth.users(id),
  papel_avaliador text not null,
  data_avaliacao timestamptz not null default now(),
  janela_inicio timestamptz,
  janela_fim timestamptz,
  metricas_antes jsonb not null default '{}'::jsonb,
  metricas_depois jsonb not null default '{}'::jsonb,
  variacoes jsonb not null default '{}'::jsonb,
  classificacao_resposta text not null check (classificacao_resposta in ('melhora','neutra','piora','inconclusiva')),
  confianca numeric check (confianca is null or (confianca >= 0 and confianca <= 100)),
  conclusao text not null,
  recomendacao_proximo_ciclo text,
  created_at timestamptz not null default now()
);

create index if not exists idx_agp_respostas_intervencao_intervencao_data on public.agp_respostas_intervencao(intervencao_id, data_avaliacao desc);
create index if not exists idx_agp_respostas_intervencao_atleta_data on public.agp_respostas_intervencao(atleta_id, data_avaliacao desc);

alter table public.agp_avaliacoes_profissionais enable row level security;
alter table public.agp_respostas_intervencao enable row level security;

drop policy if exists agp_avaliacoes_profissionais_owner on public.agp_avaliacoes_profissionais;
create policy agp_avaliacoes_profissionais_owner on public.agp_avaliacoes_profissionais
for all using (public.agp_is_owner()) with check (public.agp_is_owner());

drop policy if exists agp_respostas_intervencao_owner on public.agp_respostas_intervencao;
create policy agp_respostas_intervencao_owner on public.agp_respostas_intervencao
for all using (public.agp_is_owner()) with check (public.agp_is_owner());

grant select, insert, update on public.agp_avaliacoes_profissionais to authenticated;
grant select, insert on public.agp_respostas_intervencao to authenticated;

commit;
