-- AGP canonical decision -> intervention -> response -> learning cycle v1
-- Preserves the athlete/person as longitudinal center and does not depend on a universal score.

create table if not exists public.agp_decisoes_canonicas (
  id uuid primary key default gen_random_uuid(),
  pessoa_id uuid not null references public.agp_pessoas(id) on delete restrict,
  participante_id uuid null references public.agp_participantes_projeto(id) on delete set null,
  projeto_id uuid null references public.agp_projetos_validacao(id) on delete set null,
  ciclo_id uuid null references public.agp_ciclos_longitudinais(id) on delete set null,
  dominio text not null,
  tipo text not null check (tipo in ('tecnica','treino','recuperacao','competicao','saude','psicologia','nutricao','disponibilidade','outra')),
  decisao text not null,
  justificativa text not null,
  estado text not null default 'proposta' check (estado in ('proposta','aprovada','em_execucao','concluida','cancelada','revisao_requerida')),
  decidido_por_pessoa_id uuid not null references public.agp_pessoas(id) on delete restrict,
  papel_codigo text null references public.agp_papeis_canonicos(codigo) on delete restrict,
  competencia_codigo text null references public.agp_competencias_canonicas(codigo) on delete restrict,
  exige_validacao_profissional boolean not null default false,
  dominio_validacao text null,
  validade_ate timestamptz null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists agp_decisoes_canonicas_pessoa_idx on public.agp_decisoes_canonicas(pessoa_id,created_at desc);
create index if not exists agp_decisoes_canonicas_projeto_idx on public.agp_decisoes_canonicas(projeto_id,estado,created_at desc);

create table if not exists public.agp_decisao_evidencias (
  decisao_id uuid not null references public.agp_decisoes_canonicas(id) on delete cascade,
  tipo_evidencia text not null check (tipo_evidencia in ('coleta','metrica_observada','serie_longitudinal','sessao','competicao','avaliacao_profissional','resultado_analitico','marco','intervencao_anterior','resposta_anterior','fonte_cientifica','contexto')),
  referencia_id uuid null,
  referencia_codigo text null,
  papel text not null default 'suporte' check (papel in ('suporte','limitacao','contradicao','contexto')),
  resumo jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  primary key (decisao_id,tipo_evidencia,referencia_id,referencia_codigo,papel),
  check (referencia_id is not null or referencia_codigo is not null)
);

create table if not exists public.agp_decisao_intervencoes (
  decisao_id uuid not null references public.agp_decisoes_canonicas(id) on delete cascade,
  intervencao_id uuid not null references public.agp_intervencoes(id) on delete restrict,
  papel text not null default 'execucao' check (papel in ('execucao','complementar','substituicao')),
  created_at timestamptz not null default now(),
  primary key (decisao_id,intervencao_id)
);

create table if not exists public.agp_aprendizados_longitudinais (
  id uuid primary key default gen_random_uuid(),
  pessoa_id uuid not null references public.agp_pessoas(id) on delete restrict,
  participante_id uuid null references public.agp_participantes_projeto(id) on delete set null,
  projeto_id uuid null references public.agp_projetos_validacao(id) on delete set null,
  ciclo_id uuid null references public.agp_ciclos_longitudinais(id) on delete set null,
  decisao_id uuid null references public.agp_decisoes_canonicas(id) on delete set null,
  intervencao_id uuid null references public.agp_intervencoes(id) on delete set null,
  resposta_intervencao_id uuid null references public.agp_respostas_intervencao(id) on delete set null,
  tipo text not null check (tipo in ('fato','padrao_observado','hipotese','limitacao','resposta_a_intervencao','nao_comparavel')),
  descricao text not null,
  evidencias jsonb not null default '[]'::jsonb,
  confianca numeric null check (confianca is null or (confianca >= 0 and confianca <= 1)),
  interpretado_por text not null default 'sistema' check (interpretado_por in ('sistema','profissional','ia_governada')),
  validado_por_pessoa_id uuid null references public.agp_pessoas(id) on delete set null,
  status text not null default 'registrado' check (status in ('registrado','revisao_profissional','validado','rejeitado','superado')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists agp_aprendizados_longitudinais_pessoa_idx on public.agp_aprendizados_longitudinais(pessoa_id,created_at desc);

create or replace view public.agp_ciclo_decisao_canonico
with (security_invoker = true)
as
select
  d.id as decisao_id,
  d.pessoa_id,
  d.participante_id,
  d.projeto_id,
  d.ciclo_id,
  d.dominio,
  d.tipo,
  d.decisao,
  d.justificativa,
  d.estado as decisao_estado,
  d.exige_validacao_profissional,
  d.created_at as decisao_em,
  count(distinct de.tipo_evidencia || ':' || coalesce(de.referencia_id::text,de.referencia_codigo,'')) as evidencias_total,
  count(distinct di.intervencao_id) as intervencoes_total,
  count(distinct r.id) as respostas_total,
  count(distinct al.id) as aprendizados_total,
  case
    when count(distinct de.tipo_evidencia || ':' || coalesce(de.referencia_id::text,de.referencia_codigo,'')) = 0 then 'decisao_sem_evidencia'
    when count(distinct di.intervencao_id) = 0 then 'decisao_sem_intervencao'
    when count(distinct r.id) = 0 then 'intervencao_sem_resposta'
    when count(distinct al.id) = 0 then 'resposta_sem_aprendizado'
    else 'ciclo_fechado'
  end as estado_ciclo
from public.agp_decisoes_canonicas d
left join public.agp_decisao_evidencias de on de.decisao_id=d.id
left join public.agp_decisao_intervencoes di on di.decisao_id=d.id
left join public.agp_respostas_intervencao r on r.intervencao_id=di.intervencao_id
left join public.agp_aprendizados_longitudinais al on al.decisao_id=d.id
  or (al.intervencao_id=di.intervencao_id and al.resposta_intervencao_id=r.id)
group by d.id,d.pessoa_id,d.participante_id,d.projeto_id,d.ciclo_id,d.dominio,d.tipo,d.decisao,d.justificativa,d.estado,d.exige_validacao_profissional,d.created_at;

alter table public.agp_decisoes_canonicas enable row level security;
alter table public.agp_decisao_evidencias enable row level security;
alter table public.agp_decisao_intervencoes enable row level security;
alter table public.agp_aprendizados_longitudinais enable row level security;

revoke all on public.agp_decisoes_canonicas from public,anon,authenticated;
revoke all on public.agp_decisao_evidencias from public,anon,authenticated;
revoke all on public.agp_decisao_intervencoes from public,anon,authenticated;
revoke all on public.agp_aprendizados_longitudinais from public,anon,authenticated;
revoke all on public.agp_ciclo_decisao_canonico from public,anon,authenticated;

grant select,insert,update,delete on public.agp_decisoes_canonicas to service_role;
grant select,insert,update,delete on public.agp_decisao_evidencias to service_role;
grant select,insert,update,delete on public.agp_decisao_intervencoes to service_role;
grant select,insert,update,delete on public.agp_aprendizados_longitudinais to service_role;
grant select on public.agp_ciclo_decisao_canonico to service_role;

comment on table public.agp_decisoes_canonicas is 'Canonical human-governed decision ledger. A decision must be traceable to evidence and professional scope; no universal score is required.';
comment on table public.agp_aprendizados_longitudinais is 'Longitudinal learning ledger produced after observed response. Facts, hypotheses and limitations remain explicitly separated.';
comment on view public.agp_ciclo_decisao_canonico is 'Operational closure state for evidence -> decision -> intervention -> response -> learning.';