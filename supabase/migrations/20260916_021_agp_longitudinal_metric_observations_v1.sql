-- AGP longitudinal metric observations v1
-- Traceable facts only. No score, diagnosis or causal inference.

create or replace view public.agp_observacoes_metricas_longitudinais
with (security_invoker = true)
as
select
  c.id as ciclo_id,
  c.pessoa_id,
  c.participante_id,
  c.projeto_id,
  c.perfil_especializacao_id,
  c.nivel as nivel_ciclo,
  c.codigo as ciclo_codigo,
  cc.coleta_id,
  co.protocolo_id,
  co.instrumento_id,
  co.versao_instrumento,
  co.versao_schema,
  co.origem as origem_coleta,
  co.completude,
  co.confiabilidade,
  cm.id as observacao_id,
  cm.metrica_id,
  m.codigo as metrica_codigo,
  m.nome_canonico as metrica_nome,
  m.dominio,
  cm.metrica_versao_id,
  cm.valor_numerico,
  cm.valor_texto,
  cm.valor_json,
  cm.unidade,
  cm.contexto_medicao,
  cm.qualidade,
  coalesce(cm.measured_at, co.data_hora_coleta) as observado_em
from public.agp_ciclo_coletas cc
join public.agp_ciclos_longitudinais c on c.id = cc.ciclo_id
join public.agp_coletas co on co.id = cc.coleta_id
join public.agp_coleta_metricas cm on cm.coleta_id = co.id
join public.agp_metricas_esportivas_canonicas m on m.id = cm.metrica_id
where m.ativo = true;

create or replace view public.agp_cobertura_metricas_por_ciclo
with (security_invoker = true)
as
select
  o.ciclo_id,
  o.pessoa_id,
  o.participante_id,
  o.projeto_id,
  o.perfil_especializacao_id,
  o.nivel_ciclo,
  o.metrica_id,
  o.metrica_codigo,
  o.metrica_nome,
  o.dominio,
  count(*) as observacoes,
  count(*) filter (where o.valor_numerico is not null) as observacoes_numericas,
  count(distinct o.protocolo_id) filter (where o.protocolo_id is not null) as protocolos_distintos,
  count(distinct o.unidade) filter (where o.unidade is not null) as unidades_distintas,
  min(o.observado_em) as primeira_observacao,
  max(o.observado_em) as ultima_observacao,
  min(o.completude) as menor_completude_coleta,
  min(o.confiabilidade) filter (where o.confiabilidade is not null) as menor_confiabilidade_coleta,
  case
    when count(*) = 0 then 'sem_dados'
    when count(distinct o.unidade) filter (where o.unidade is not null) > 1 then 'requer_revisao_unidade'
    when count(distinct o.protocolo_id) filter (where o.protocolo_id is not null) > 1 then 'requer_revisao_protocolo'
    else 'serie_estruturalmente_coerente'
  end as estado_comparabilidade_estrutural
from public.agp_observacoes_metricas_longitudinais o
group by
  o.ciclo_id,o.pessoa_id,o.participante_id,o.projeto_id,o.perfil_especializacao_id,o.nivel_ciclo,
  o.metrica_id,o.metrica_codigo,o.metrica_nome,o.dominio;

revoke all on public.agp_observacoes_metricas_longitudinais from public, anon, authenticated;
revoke all on public.agp_cobertura_metricas_por_ciclo from public, anon, authenticated;
grant select on public.agp_observacoes_metricas_longitudinais to service_role;
grant select on public.agp_cobertura_metricas_por_ciclo to service_role;
