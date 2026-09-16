-- AGP individual longitudinal intelligence facts v1
-- Facts, comparability and explicit professional/operational signals only.
-- No universal score, no causal inference, no automatic better/worse judgment.

create or replace view public.agp_series_metricas_longitudinais
with (security_invoker = true)
as
select
  o.pessoa_id,
  o.participante_id,
  o.projeto_id,
  o.perfil_especializacao_id,
  o.metrica_id,
  o.metrica_codigo,
  o.metrica_nome,
  o.dominio,
  o.metrica_versao_id,
  o.protocolo_id,
  o.instrumento_id,
  o.versao_instrumento,
  o.versao_schema,
  o.unidade,
  md5(
    concat_ws('|',
      o.metrica_id::text,
      coalesce(o.metrica_versao_id::text,''),
      coalesce(o.protocolo_id::text,''),
      coalesce(o.instrumento_id::text,''),
      coalesce(o.versao_instrumento,''),
      coalesce(o.versao_schema,''),
      coalesce(o.unidade,''),
      coalesce(o.contexto_medicao::text,'{}')
    )
  ) as assinatura_comparabilidade,
  count(*) as observacoes,
  count(*) filter (where o.valor_numerico is not null) as observacoes_numericas,
  min(o.observado_em) as primeira_observacao,
  max(o.observado_em) as ultima_observacao,
  min(o.completude) as menor_completude,
  min(o.confiabilidade) filter (where o.confiabilidade is not null) as menor_confiabilidade,
  case
    when count(*) filter (where o.valor_numerico is not null) >= 2 then 'comparavel_estritamente'
    when count(*) >= 1 then 'evidencia_sem_par_comparavel'
    else 'sem_dados'
  end as estado_serie
from public.agp_observacoes_metricas_longitudinais o
group by
  o.pessoa_id,o.participante_id,o.projeto_id,o.perfil_especializacao_id,
  o.metrica_id,o.metrica_codigo,o.metrica_nome,o.dominio,
  o.metrica_versao_id,o.protocolo_id,o.instrumento_id,o.versao_instrumento,
  o.versao_schema,o.unidade,o.contexto_medicao;

create or replace view public.agp_mudancas_metricas_longitudinais
with (security_invoker = true)
as
with base as (
  select
    o.*,
    md5(
      concat_ws('|',
        o.metrica_id::text,
        coalesce(o.metrica_versao_id::text,''),
        coalesce(o.protocolo_id::text,''),
        coalesce(o.instrumento_id::text,''),
        coalesce(o.versao_instrumento,''),
        coalesce(o.versao_schema,''),
        coalesce(o.unidade,''),
        coalesce(o.contexto_medicao::text,'{}')
      )
    ) as assinatura_comparabilidade
  from public.agp_observacoes_metricas_longitudinais o
  where o.valor_numerico is not null
), ordered as (
  select
    b.*,
    lag(b.valor_numerico) over (
      partition by b.pessoa_id,b.metrica_id,b.assinatura_comparabilidade
      order by b.observado_em,b.observacao_id
    ) as valor_anterior,
    lag(b.observado_em) over (
      partition by b.pessoa_id,b.metrica_id,b.assinatura_comparabilidade
      order by b.observado_em,b.observacao_id
    ) as observado_anterior_em,
    lag(b.observacao_id) over (
      partition by b.pessoa_id,b.metrica_id,b.assinatura_comparabilidade
      order by b.observado_em,b.observacao_id
    ) as observacao_anterior_id
  from base b
)
select
  pessoa_id,participante_id,projeto_id,perfil_especializacao_id,
  metrica_id,metrica_codigo,metrica_nome,dominio,
  assinatura_comparabilidade,
  observacao_anterior_id,
  observacao_id as observacao_atual_id,
  observado_anterior_em,
  observado_em as observado_atual_em,
  valor_anterior,
  valor_numerico as valor_atual,
  unidade,
  (valor_numerico - valor_anterior) as delta_absoluto,
  case
    when valor_anterior is null or valor_anterior = 0 then null
    else round(((valor_numerico - valor_anterior) / abs(valor_anterior)) * 100, 4)
  end as delta_percentual,
  case
    when valor_anterior is null then 'sem_comparacao_anterior'
    when valor_numerico > valor_anterior then 'aumento_nominal'
    when valor_numerico < valor_anterior then 'reducao_nominal'
    else 'sem_mudanca_nominal'
  end as direcao_nominal,
  'nao_interpretada'::text as significado_esportivo,
  protocolo_id,instrumento_id,versao_instrumento,versao_schema,
  completude,confiabilidade,qualidade,contexto_medicao
from ordered
where valor_anterior is not null;

create or replace view public.agp_sinais_explicitos_individuais
with (security_invoker = true)
as
select
  pp.pessoa_id,
  a.participante_id,
  a.projeto_id,
  a.data_avaliacao as ocorrido_em,
  'restricao_profissional'::text as tipo,
  a.id as referencia_id,
  a.dominio,
  a.papel_profissional as responsavel_papel,
  jsonb_build_object(
    'restricoes', a.restricoes,
    'recomendacoes', a.recomendacoes,
    'achados', a.achados,
    'confianca', a.confianca,
    'validade_ate', a.validade_ate,
    'status', a.status
  ) as contexto
from public.agp_avaliacoes_profissionais a
join public.agp_participantes_projeto pp on pp.id = a.participante_id
where a.status = 'validada'
  and coalesce(a.restricoes, '{}'::jsonb) not in ('{}'::jsonb, '[]'::jsonb)
  and (a.validade_ate is null or a.validade_ate >= now())
union all
select
  pp.pessoa_id,
  pp.id as participante_id,
  i.projeto_id,
  i.inicio as ocorrido_em,
  'intervencao_ativa'::text as tipo,
  i.id as referencia_id,
  i.dominio,
  i.papel_responsavel as responsavel_papel,
  jsonb_build_object(
    'descricao', i.descricao,
    'justificativa', i.justificativa,
    'resultado_esperado', i.resultado_esperado,
    'fim_previsto', i.fim_previsto,
    'status', i.status
  ) as contexto
from public.agp_intervencoes i
join public.agp_perfis_esportivos pe on pe.legacy_perfil_atleta_id = i.atleta_id
join public.agp_participantes_projeto pp on pp.pessoa_id = pe.pessoa_id
  and (i.projeto_id is null or pp.projeto_id = i.projeto_id)
where i.status in ('aprovada','em_execucao')
  and pp.ativo = true;

create or replace view public.agp_estado_inteligencia_longitudinal_individual
with (security_invoker = true)
as
select
  p.id as pessoa_id,
  (select count(*) from public.agp_ciclos_longitudinais c where c.pessoa_id=p.id) as ciclos_total,
  (select count(*) from public.agp_ciclos_longitudinais c where c.pessoa_id=p.id and c.status='ativo') as ciclos_ativos,
  (select count(*) from public.agp_observacoes_metricas_longitudinais o where o.pessoa_id=p.id) as observacoes_total,
  (select count(*) from public.agp_series_metricas_longitudinais s where s.pessoa_id=p.id and s.estado_serie='comparavel_estritamente') as series_comparaveis,
  (select count(*) from public.agp_mudancas_metricas_longitudinais m where m.pessoa_id=p.id) as mudancas_observadas,
  (select count(*) from public.agp_sinais_explicitos_individuais x where x.pessoa_id=p.id and x.tipo='restricao_profissional') as restricoes_profissionais_ativas,
  (select count(*) from public.agp_sinais_explicitos_individuais x where x.pessoa_id=p.id and x.tipo='intervencao_ativa') as intervencoes_ativas,
  case
    when (select count(*) from public.agp_observacoes_metricas_longitudinais o where o.pessoa_id=p.id)=0
      then 'dados_insuficientes'
    when (select count(*) from public.agp_series_metricas_longitudinais s where s.pessoa_id=p.id and s.estado_serie='comparavel_estritamente')=0
      then 'evidencia_sem_serie_comparavel'
    else 'base_longitudinal_comparavel'
  end as estado_base
from public.agp_pessoas p;

revoke all on public.agp_series_metricas_longitudinais from public, anon, authenticated;
revoke all on public.agp_mudancas_metricas_longitudinais from public, anon, authenticated;
revoke all on public.agp_sinais_explicitos_individuais from public, anon, authenticated;
revoke all on public.agp_estado_inteligencia_longitudinal_individual from public, anon, authenticated;
grant select on public.agp_series_metricas_longitudinais to service_role;
grant select on public.agp_mudancas_metricas_longitudinais to service_role;
grant select on public.agp_sinais_explicitos_individuais to service_role;
grant select on public.agp_estado_inteligencia_longitudinal_individual to service_role;
