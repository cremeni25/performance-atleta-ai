-- AGP individual longitudinal intelligence v1
-- Facts first. No universal score. No causal claim from temporal proximity.

create table if not exists public.agp_interpretacoes_longitudinais (
  id uuid primary key default gen_random_uuid(),
  pessoa_id uuid not null references public.agp_pessoas(id) on delete cascade,
  participante_id uuid null references public.agp_participantes_projeto(id) on delete set null,
  projeto_id uuid null references public.agp_projetos_validacao(id) on delete set null,
  ciclo_id uuid null references public.agp_ciclos_longitudinais(id) on delete set null,
  metrica_id uuid null references public.agp_metricas_esportivas_canonicas(id) on delete restrict,
  tipo_saida text not null check (tipo_saida in ('fato','inferencia','hipotese','suporte_decisao')),
  estado text not null check (estado in ('dados_insuficientes','nao_comparavel','observado','revisao_requerida','validado_profissionalmente')),
  janela_inicio timestamptz null,
  janela_fim timestamptz null,
  evidencias jsonb not null default '[]'::jsonb,
  explicacao text not null,
  confianca numeric null check (confianca is null or (confianca >= 0 and confianca <= 1)),
  limitacoes text null,
  versao_motor text not null,
  validado_por_auth_id uuid null,
  validado_em timestamptz null,
  created_at timestamptz not null default now()
);

create index if not exists agp_interpretacoes_longitudinais_pessoa_idx
  on public.agp_interpretacoes_longitudinais(pessoa_id, created_at desc);
create index if not exists agp_interpretacoes_longitudinais_metrica_idx
  on public.agp_interpretacoes_longitudinais(metrica_id, created_at desc);

alter table public.agp_interpretacoes_longitudinais enable row level security;
revoke all on public.agp_interpretacoes_longitudinais from public, anon, authenticated;
grant select, insert, update, delete on public.agp_interpretacoes_longitudinais to service_role;

create or replace view public.agp_series_longitudinais_metricas
with (security_invoker = true)
as
with obs as (
  select
    pp.pessoa_id,
    c.participante_id,
    c.projeto_id,
    cm.metrica_id,
    m.codigo as metrica_codigo,
    m.nome_canonico,
    m.dominio,
    coalesce(cm.measured_at, c.data_hora_coleta) as medido_em,
    cm.valor_numerico,
    cm.unidade,
    c.protocolo_id,
    cm.metrica_versao_id,
    c.completude,
    c.confiabilidade,
    cm.contexto_medicao,
    cm.qualidade,
    c.id as coleta_id,
    cm.id as coleta_metrica_id
  from public.agp_coleta_metricas cm
  join public.agp_coletas c on c.id = cm.coleta_id
  join public.agp_participantes_projeto pp on pp.id = c.participante_id
  join public.agp_metricas_esportivas_canonicas m on m.id = cm.metrica_id
  where c.status = 'validada'
    and cm.valor_numerico is not null
), grouped as (
  select
    pessoa_id,
    participante_id,
    projeto_id,
    metrica_id,
    metrica_codigo,
    nome_canonico,
    dominio,
    count(*)::integer as amostras,
    min(medido_em) as primeira_medicao_em,
    max(medido_em) as ultima_medicao_em,
    count(distinct unidade)::integer as unidades_distintas,
    count(distinct protocolo_id) filter (where protocolo_id is not null)::integer as protocolos_distintos,
    count(distinct metrica_versao_id) filter (where metrica_versao_id is not null)::integer as versoes_metricas_distintas,
    avg(completude)::numeric as completude_media,
    avg(confiabilidade) filter (where confiabilidade is not null)::numeric as confiabilidade_media,
    (array_agg(valor_numerico order by medido_em asc))[1] as primeiro_valor,
    (array_agg(valor_numerico order by medido_em desc))[1] as ultimo_valor,
    (array_agg(unidade order by medido_em desc))[1] as unidade_atual,
    (array_agg(protocolo_id order by medido_em desc))[1] as protocolo_atual_id
  from obs
  group by pessoa_id, participante_id, projeto_id, metrica_id, metrica_codigo, nome_canonico, dominio
)
select
  g.*,
  case
    when g.amostras < 2 then 'dados_insuficientes'
    when g.unidades_distintas > 1 then 'nao_comparavel'
    when g.protocolos_distintos > 1 then 'revisao_requerida'
    when g.versoes_metricas_distintas > 1 then 'revisao_requerida'
    else 'comparavel'
  end as estado_comparabilidade,
  case
    when g.amostras >= 2
      and g.unidades_distintas <= 1
      and g.protocolos_distintos <= 1
      and g.versoes_metricas_distintas <= 1
    then g.ultimo_valor - g.primeiro_valor
    else null
  end as delta_absoluto,
  case
    when g.amostras >= 2
      and g.unidades_distintas <= 1
      and g.protocolos_distintos <= 1
      and g.versoes_metricas_distintas <= 1
      and g.primeiro_valor <> 0
    then ((g.ultimo_valor - g.primeiro_valor) / abs(g.primeiro_valor)) * 100
    else null
  end as delta_percentual
from grouped g;

revoke all on public.agp_series_longitudinais_metricas from public, anon, authenticated;
grant select on public.agp_series_longitudinais_metricas to service_role;

create or replace view public.agp_estado_longitudinal_individual
with (security_invoker = true)
as
select
  p.id as pessoa_id,
  count(distinct c.id) as ciclos_total,
  count(distinct c.id) filter (where c.nivel = 'dia') as dias,
  count(distinct c.id) filter (where c.nivel = 'microciclo') as microciclos,
  count(distinct c.id) filter (where c.nivel = 'mesociclo') as mesociclos,
  count(distinct c.id) filter (where c.nivel = 'temporada') as temporadas,
  count(distinct c.id) filter (where c.nivel = 'carreira') as carreiras,
  count(distinct ml.id) as marcos,
  count(distinct s.metrica_id) as metricas_observadas,
  count(distinct s.metrica_id) filter (where s.estado_comparabilidade = 'comparavel') as metricas_comparaveis,
  count(distinct s.metrica_id) filter (where s.estado_comparabilidade = 'dados_insuficientes') as metricas_com_dados_insuficientes,
  count(distinct s.metrica_id) filter (where s.estado_comparabilidade in ('nao_comparavel','revisao_requerida')) as metricas_requerendo_revisao,
  case
    when count(distinct s.metrica_id) = 0 then 'sem_evidencia_longitudinal'
    when count(distinct s.metrica_id) filter (where s.estado_comparabilidade = 'comparavel') = 0 then 'evidencia_em_formacao'
    else 'longitudinalidade_observavel'
  end as estado
from public.agp_pessoas p
left join public.agp_ciclos_longitudinais c on c.pessoa_id = p.id
left join public.agp_marcos_longitudinais ml on ml.pessoa_id = p.id
left join public.agp_series_longitudinais_metricas s on s.pessoa_id = p.id
group by p.id;

revoke all on public.agp_estado_longitudinal_individual from public, anon, authenticated;
grant select on public.agp_estado_longitudinal_individual to service_role;
