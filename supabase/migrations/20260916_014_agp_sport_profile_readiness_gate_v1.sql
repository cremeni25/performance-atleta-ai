create or replace view public.agp_status_prontidao_perfil_esportivo
with (security_invoker = true)
as
with metricas as (
  select pem.perfil_especializacao_id, m.id as metrica_id
  from public.agp_perfil_especializacao_metricas pem
  join public.agp_metricas_esportivas_canonicas m on m.id = pem.metrica_id
  where m.ativo = true
), protocolos as (
  select distinct me.perfil_especializacao_id, mp.protocolo_id
  from metricas me
  join public.agp_metrica_protocolos mp on mp.metrica_id = me.metrica_id
), fontes as (
  select distinct me.perfil_especializacao_id, mf.fonte_id
  from metricas me
  join public.agp_metrica_fontes mf on mf.metrica_id = me.metrica_id
  union
  select distinct pr.perfil_especializacao_id, pf.fonte_id
  from protocolos pr
  join public.agp_protocolo_fontes pf on pf.protocolo_id = pr.protocolo_id
  union
  select distinct pef.perfil_especializacao_id, pef.fonte_id
  from public.agp_perfil_especializacao_fontes pef
), metric_counts as (
  select p.id as perfil_id,
         count(distinct me.metrica_id) as metricas_total,
         count(distinct me.metrica_id) filter (where exists (
           select 1 from public.agp_metrica_versoes mv
           where mv.metrica_id = me.metrica_id and mv.versao = p.versao
         )) as metricas_com_versao,
         count(distinct me.metrica_id) filter (where exists (
           select 1 from public.agp_metrica_fontes mf where mf.metrica_id = me.metrica_id
         )) as metricas_com_fonte,
         count(distinct me.metrica_id) filter (where exists (
           select 1 from public.agp_metrica_protocolos mp where mp.metrica_id = me.metrica_id
         )) as metricas_com_protocolo
  from public.agp_perfis_especializacao_esportiva p
  left join metricas me on me.perfil_especializacao_id = p.id
  group by p.id
), protocol_counts as (
  select p.id as perfil_id,
         count(distinct pr.protocolo_id) as protocolos_total,
         count(distinct pr.protocolo_id) filter (where exists (
           select 1 from public.agp_protocolo_fontes pf where pf.protocolo_id = pr.protocolo_id
         )) as protocolos_com_fonte
  from public.agp_perfis_especializacao_esportiva p
  left join protocolos pr on pr.perfil_especializacao_id = p.id
  group by p.id
), source_counts as (
  select p.id as perfil_id,
         count(distinct f.fonte_id) as fontes_referenciadas,
         count(distinct f.fonte_id) filter (where exists (
           select 1 from public.agp_revisoes_fontes_cientificas r
           where r.fonte_id = f.fonte_id
             and r.tipo_revisao = 'bibliografica'
             and r.status in ('verificada','aprovada')
         )) as fontes_bibliograficamente_verificadas,
         count(distinct f.fonte_id) filter (where exists (
           select 1 from public.agp_revisoes_fontes_cientificas r
           where r.fonte_id = f.fonte_id
             and r.tipo_revisao = 'metodologica'
             and r.status in ('verificada','aprovada')
         )) as fontes_metodologicamente_verificadas,
         count(distinct f.fonte_id) filter (where exists (
           select 1 from public.agp_fontes_cientificas fc
           where fc.id = f.fonte_id and fc.status_validacao = 'validada'
         )) as fontes_profissionalmente_validadas
  from public.agp_perfis_especializacao_esportiva p
  left join fontes f on f.perfil_especializacao_id = p.id
  group by p.id
)
select p.id as perfil_id,
       p.codigo,
       p.versao,
       p.status_catalogo,
       mc.metricas_total,
       mc.metricas_com_versao,
       mc.metricas_com_fonte,
       mc.metricas_com_protocolo,
       pc.protocolos_total,
       pc.protocolos_com_fonte,
       sc.fontes_referenciadas,
       sc.fontes_bibliograficamente_verificadas,
       sc.fontes_metodologicamente_verificadas,
       sc.fontes_profissionalmente_validadas,
       (
         mc.metricas_total > 0
         and mc.metricas_total = mc.metricas_com_versao
         and mc.metricas_total = mc.metricas_com_fonte
         and mc.metricas_total = mc.metricas_com_protocolo
         and pc.protocolos_total > 0
         and pc.protocolos_total = pc.protocolos_com_fonte
         and sc.fontes_referenciadas > 0
         and sc.fontes_referenciadas = sc.fontes_bibliograficamente_verificadas
         and sc.fontes_referenciadas = sc.fontes_metodologicamente_verificadas
         and sc.fontes_referenciadas = sc.fontes_profissionalmente_validadas
       ) as pronto_publicacao,
       jsonb_strip_nulls(jsonb_build_object(
         'metricas_sem_versao', nullif(mc.metricas_total - mc.metricas_com_versao, 0),
         'metricas_sem_fonte', nullif(mc.metricas_total - mc.metricas_com_fonte, 0),
         'metricas_sem_protocolo', nullif(mc.metricas_total - mc.metricas_com_protocolo, 0),
         'protocolos_sem_fonte', nullif(pc.protocolos_total - pc.protocolos_com_fonte, 0),
         'fontes_sem_verificacao_bibliografica', nullif(sc.fontes_referenciadas - sc.fontes_bibliograficamente_verificadas, 0),
         'fontes_sem_revisao_metodologica', nullif(sc.fontes_referenciadas - sc.fontes_metodologicamente_verificadas, 0),
         'fontes_sem_validacao_profissional', nullif(sc.fontes_referenciadas - sc.fontes_profissionalmente_validadas, 0)
       )) as bloqueios
from public.agp_perfis_especializacao_esportiva p
join metric_counts mc on mc.perfil_id = p.id
join protocol_counts pc on pc.perfil_id = p.id
join source_counts sc on sc.perfil_id = p.id;

revoke all on public.agp_status_prontidao_perfil_esportivo from public, anon, authenticated;
grant select on public.agp_status_prontidao_perfil_esportivo to service_role;
