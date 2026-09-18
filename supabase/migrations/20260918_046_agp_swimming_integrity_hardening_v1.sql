-- AGP Swimming integrity hardening v1
-- 1) Materialize daily readiness items as traceable canonical metrics.
-- 2) Provide a conservative longitudinal series view with explicit context signature.
-- 3) Preserve person-level continuity across project/participant changes without conflating incompatible contexts.

insert into public.agp_metricas_esportivas_canonicas
(codigo,nome_canonico,dominio,tipo_dado,unidade_canonica,origem_preferencial,formula,requisitos_calculo,regras_qualidade,limites_interpretacao)
values
('AGP_READINESS_SLEEP_HOURS','Sleep duration reported','recovery_context','bruto','h','athlete_self_report','{}','[]','{"self_report":true,"scale_version_required":true}','Autodeclared sleep duration. Contextual evidence only; not a diagnosis and not a standalone readiness verdict.'),
('AGP_READINESS_SLEEP_QUALITY','Sleep quality reported','recovery_context','bruto','1-5','athlete_self_report','{}','[]','{"self_report":true,"scale_version_required":true}','Autodeclared sleep quality. Interpret longitudinally and in context; no universal cutoff is implied.'),
('AGP_READINESS_FATIGUE','Fatigue reported','recovery_context','bruto','1-5','athlete_self_report','{}','[]','{"self_report":true,"scale_version_required":true}','Autodeclared fatigue. Contextual signal only; do not infer pathology or training risk from one value.'),
('AGP_READINESS_PAIN','Pain/discomfort reported','recovery_context','bruto','0-10','athlete_self_report','{}','[]','{"self_report":true,"scale_version_required":true}','Autodeclared pain/discomfort. Does not constitute diagnosis or clinical clearance.'),
('AGP_READINESS_STRESS','Stress reported','contextual','bruto','1-5','athlete_self_report','{}','[]','{"self_report":true,"scale_version_required":true}','Autodeclared stress. Interpret only with context and appropriate professional scope.'),
('AGP_READINESS_MOOD','Mood reported','contextual','bruto','1-5','athlete_self_report','{}','[]','{"self_report":true,"scale_version_required":true}','Autodeclared mood. Not a psychological diagnosis.'),
('AGP_READINESS_LAST_SESSION_RPE','Last session perceived exertion reported','internal_load','bruto','0-10','athlete_self_report','{}','[]','{"self_report":true,"scale_version_required":true}','Athlete recall of perceived effort of the last session. Keep distinct from an objectively linked session RPE unless session linkage is known.')
on conflict (codigo) do update set
  nome_canonico=excluded.nome_canonico,
  dominio=excluded.dominio,
  tipo_dado=excluded.tipo_dado,
  unidade_canonica=excluded.unidade_canonica,
  origem_preferencial=excluded.origem_preferencial,
  regras_qualidade=excluded.regras_qualidade,
  limites_interpretacao=excluded.limites_interpretacao,
  updated_at=now();

create or replace view public.agp_series_longitudinais_metricas_v2
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
    m.regras_qualidade,
    coalesce(cm.measured_at, c.data_hora_coleta) as medido_em,
    cm.valor_numerico,
    cm.unidade,
    c.protocolo_id,
    cm.metrica_versao_id,
    c.completude,
    c.confiabilidade,
    cm.contexto_medicao,
    cm.qualidade,
    md5(concat_ws('|',
      cm.metrica_id::text,
      coalesce(cm.metrica_versao_id::text,''),
      coalesce(c.protocolo_id::text,''),
      coalesce(cm.unidade,''),
      coalesce(cm.contexto_medicao::text,'{}')
    )) as assinatura_contexto,
    case
      when coalesce(m.regras_qualidade,'{}'::jsonb) = '{}'::jsonb then true
      when coalesce(cm.contexto_medicao,'{}'::jsonb) <> '{}'::jsonb then true
      else false
    end as contexto_minimo_presente
  from public.agp_coleta_metricas cm
  join public.agp_coletas c on c.id = cm.coleta_id
  join public.agp_participantes_projeto pp on pp.id = c.participante_id
  join public.agp_metricas_esportivas_canonicas m on m.id = cm.metrica_id
  where c.status = 'validada'
    and cm.valor_numerico is not null
    and m.ativo = true
), grouped as (
  select
    pessoa_id,
    metrica_id,
    metrica_codigo,
    nome_canonico,
    dominio,
    assinatura_contexto,
    count(*)::integer as amostras,
    min(medido_em) as primeira_medicao_em,
    max(medido_em) as ultima_medicao_em,
    count(distinct participante_id)::integer as vinculos_participante_distintos,
    count(distinct projeto_id)::integer as projetos_distintos,
    count(distinct unidade)::integer as unidades_distintas,
    count(distinct protocolo_id) filter (where protocolo_id is not null)::integer as protocolos_distintos,
    count(distinct metrica_versao_id) filter (where metrica_versao_id is not null)::integer as versoes_metricas_distintas,
    avg(completude)::numeric as completude_media,
    avg(confiabilidade) filter (where confiabilidade is not null)::numeric as confiabilidade_media,
    bool_and(contexto_minimo_presente) as contexto_minimo_presente,
    (array_agg(valor_numerico order by medido_em asc))[1] as primeiro_valor,
    (array_agg(valor_numerico order by medido_em desc))[1] as ultimo_valor,
    (array_agg(unidade order by medido_em desc))[1] as unidade_atual,
    (array_agg(protocolo_id order by medido_em desc))[1] as protocolo_atual_id,
    (array_agg(participante_id order by medido_em desc))[1] as participante_id_atual,
    (array_agg(projeto_id order by medido_em desc))[1] as projeto_id_atual
  from obs
  group by pessoa_id,metrica_id,metrica_codigo,nome_canonico,dominio,assinatura_contexto
)
select
  g.*,
  case
    when g.amostras < 2 then 'dados_insuficientes'
    when not g.contexto_minimo_presente then 'revisao_requerida'
    when g.unidades_distintas > 1 then 'nao_comparavel'
    when g.protocolos_distintos > 1 then 'revisao_requerida'
    when g.versoes_metricas_distintas > 1 then 'revisao_requerida'
    else 'comparavel'
  end as estado_comparabilidade,
  case
    when g.amostras >= 2
      and g.contexto_minimo_presente
      and g.unidades_distintas <= 1
      and g.protocolos_distintos <= 1
      and g.versoes_metricas_distintas <= 1
    then g.ultimo_valor - g.primeiro_valor
    else null
  end as delta_absoluto,
  case
    when g.amostras >= 2
      and g.contexto_minimo_presente
      and g.unidades_distintas <= 1
      and g.protocolos_distintos <= 1
      and g.versoes_metricas_distintas <= 1
      and g.primeiro_valor <> 0
    then ((g.ultimo_valor - g.primeiro_valor) / abs(g.primeiro_valor)) * 100
    else null
  end as delta_percentual
from grouped g;

revoke all on public.agp_series_longitudinais_metricas_v2 from public, anon, authenticated;
grant select on public.agp_series_longitudinais_metricas_v2 to service_role;

comment on view public.agp_series_longitudinais_metricas_v2 is
'Conservative person-level longitudinal metric series. Comparison occurs only inside identical metric/protocol/unit/context signatures; project transitions do not reset person history, while incompatible contexts remain separated.';
