-- AGP canonical institutional intelligence v1
-- Institution/project intelligence is built from individual longitudinal states and operational coverage.
-- No ranking of athletes. No global performance score. No causal claim.

create or replace view public.agp_inteligencia_projeto_canonica
with (security_invoker = true)
as
select
  pr.id as projeto_id,
  pr.instituicao_id,
  pr.nome as projeto_nome,
  pr.status as projeto_status,
  coalesce((
    select count(*)
    from public.agp_participantes_projeto pp
    where pp.projeto_id = pr.id and pp.ativo = true
  ),0)::bigint as participantes_ativos,
  coalesce((
    select count(*)
    from public.agp_participantes_projeto pp
    where pp.projeto_id = pr.id and pp.ativo = true
      and coalesce(pp.funcao_canonica_codigo, case when pp.funcao_no_projeto='atleta' then 'athlete' end) = 'athlete'
  ),0)::bigint as atletas_ativos,
  coalesce((
    select count(*)
    from public.agp_participantes_projeto pp
    join public.agp_papeis_canonicos pc on pc.codigo = pp.funcao_canonica_codigo
    where pp.projeto_id = pr.id and pp.ativo = true and pc.familia='equipe_tecnica'
  ),0)::bigint as equipe_tecnica_ativa,
  coalesce((
    select count(*)
    from public.agp_participantes_projeto pp
    join public.agp_papeis_canonicos pc on pc.codigo = pp.funcao_canonica_codigo
    where pp.projeto_id = pr.id and pp.ativo = true and pc.familia='especialista'
  ),0)::bigint as especialistas_ativos,
  coalesce((
    select count(*)
    from public.agp_participantes_projeto pp
    join public.agp_estado_longitudinal_individual e on e.pessoa_id = pp.pessoa_id
    where pp.projeto_id = pr.id and pp.ativo = true
      and coalesce(pp.funcao_canonica_codigo, case when pp.funcao_no_projeto='atleta' then 'athlete' end) = 'athlete'
      and e.estado='sem_evidencia_longitudinal'
  ),0)::bigint as atletas_sem_evidencia_longitudinal,
  coalesce((
    select count(*)
    from public.agp_participantes_projeto pp
    join public.agp_estado_longitudinal_individual e on e.pessoa_id = pp.pessoa_id
    where pp.projeto_id = pr.id and pp.ativo = true
      and coalesce(pp.funcao_canonica_codigo, case when pp.funcao_no_projeto='atleta' then 'athlete' end) = 'athlete'
      and e.estado='evidencia_em_formacao'
  ),0)::bigint as atletas_evidencia_em_formacao,
  coalesce((
    select count(*)
    from public.agp_participantes_projeto pp
    join public.agp_estado_longitudinal_individual e on e.pessoa_id = pp.pessoa_id
    where pp.projeto_id = pr.id and pp.ativo = true
      and coalesce(pp.funcao_canonica_codigo, case when pp.funcao_no_projeto='atleta' then 'athlete' end) = 'athlete'
      and e.estado='longitudinalidade_observavel'
  ),0)::bigint as atletas_longitudinalidade_observavel,
  coalesce((
    select sum(e.metricas_requerendo_revisao)
    from public.agp_participantes_projeto pp
    join public.agp_estado_longitudinal_individual e on e.pessoa_id = pp.pessoa_id
    where pp.projeto_id = pr.id and pp.ativo = true
      and coalesce(pp.funcao_canonica_codigo, case when pp.funcao_no_projeto='atleta' then 'athlete' end) = 'athlete'
  ),0)::bigint as series_metricas_requerendo_revisao,
  coalesce((select count(*) from public.agp_sessoes_esportivas s where s.projeto_id=pr.id),0)::bigint as sessoes_total,
  coalesce((select count(*) from public.agp_sessoes_esportivas s where s.projeto_id=pr.id and s.status='concluida'),0)::bigint as sessoes_concluidas,
  coalesce((select count(*) from public.agp_sessoes_esportivas s where s.projeto_id=pr.id and s.status in ('planejada','em_execucao')),0)::bigint as sessoes_abertas,
  coalesce((select count(*) from public.agp_competicoes c where c.projeto_id=pr.id),0)::bigint as competicoes_total,
  coalesce((select count(*) from public.agp_competicoes c where c.projeto_id=pr.id and c.status='concluida'),0)::bigint as competicoes_concluidas,
  coalesce((
    select count(*)
    from public.agp_participacoes_prova ppv
    join public.agp_provas_competicao pv on pv.id=ppv.prova_id
    join public.agp_competicoes c on c.id=pv.competicao_id
    where c.projeto_id=pr.id and ppv.status='realizado'
  ),0)::bigint as participacoes_prova_realizadas,
  coalesce((select count(*) from public.agp_coletas c where c.projeto_id=pr.id),0)::bigint as coletas_total,
  coalesce((select count(*) from public.agp_coletas c where c.projeto_id=pr.id and c.status='validada'),0)::bigint as coletas_validadas,
  case
    when coalesce((select count(*) from public.agp_participantes_projeto pp where pp.projeto_id=pr.id and pp.ativo=true and coalesce(pp.funcao_canonica_codigo, case when pp.funcao_no_projeto='atleta' then 'athlete' end)='athlete'),0)=0
      then 'sem_atletas_ativos'
    when coalesce((select count(*) from public.agp_participantes_projeto pp join public.agp_estado_longitudinal_individual e on e.pessoa_id=pp.pessoa_id where pp.projeto_id=pr.id and pp.ativo=true and coalesce(pp.funcao_canonica_codigo, case when pp.funcao_no_projeto='atleta' then 'athlete' end)='athlete' and e.estado='longitudinalidade_observavel'),0)>0
      then 'longitudinalidade_em_operacao'
    when coalesce((select count(*) from public.agp_coletas c where c.projeto_id=pr.id and c.status='validada'),0)>0
      then 'evidencia_em_formacao'
    else 'aguardando_evidencia_operacional'
  end as estado_operacional
from public.agp_projetos_validacao pr;

create or replace view public.agp_inteligencia_institucional_canonica
with (security_invoker = true)
as
select
  i.id as instituicao_id,
  coalesce(i.nome_exibicao,i.nome) as instituicao_nome,
  i.status as instituicao_status,
  count(p.projeto_id)::bigint as projetos_total,
  count(p.projeto_id) filter (where p.projeto_status='ativo')::bigint as projetos_ativos,
  coalesce(sum(p.atletas_ativos),0)::bigint as atletas_ativos,
  coalesce(sum(p.equipe_tecnica_ativa),0)::bigint as equipe_tecnica_ativa,
  coalesce(sum(p.especialistas_ativos),0)::bigint as especialistas_ativos,
  coalesce(sum(p.atletas_sem_evidencia_longitudinal),0)::bigint as atletas_sem_evidencia_longitudinal,
  coalesce(sum(p.atletas_evidencia_em_formacao),0)::bigint as atletas_evidencia_em_formacao,
  coalesce(sum(p.atletas_longitudinalidade_observavel),0)::bigint as atletas_longitudinalidade_observavel,
  coalesce(sum(p.series_metricas_requerendo_revisao),0)::bigint as series_metricas_requerendo_revisao,
  coalesce(sum(p.sessoes_total),0)::bigint as sessoes_total,
  coalesce(sum(p.competicoes_total),0)::bigint as competicoes_total,
  coalesce(sum(p.coletas_total),0)::bigint as coletas_total,
  coalesce(sum(p.coletas_validadas),0)::bigint as coletas_validadas,
  case
    when coalesce(sum(p.atletas_ativos),0)=0 then 'sem_atletas_ativos'
    when coalesce(sum(p.atletas_longitudinalidade_observavel),0)>0 then 'longitudinalidade_em_operacao'
    when coalesce(sum(p.coletas_validadas),0)>0 then 'evidencia_em_formacao'
    else 'aguardando_evidencia_operacional'
  end as estado_operacional
from public.agp_instituicoes i
left join public.agp_inteligencia_projeto_canonica p on p.instituicao_id=i.id
group by i.id,i.nome_exibicao,i.nome,i.status;

revoke all on public.agp_inteligencia_projeto_canonica from public, anon, authenticated;
revoke all on public.agp_inteligencia_institucional_canonica from public, anon, authenticated;
grant select on public.agp_inteligencia_projeto_canonica to service_role;
grant select on public.agp_inteligencia_institucional_canonica to service_role;

comment on view public.agp_inteligencia_projeto_canonica is
'Project-level institutional intelligence without athlete ranking or universal performance score. Aggregates longitudinal readiness of evidence and operational coverage.';
comment on view public.agp_inteligencia_institucional_canonica is
'Institution-level canonical intelligence derived from project/individual longitudinal states. Designed for governance and resource/action visibility, not athlete ranking.';
