with p as (
  select id
  from public.agp_perfis_especializacao_esportiva
  where codigo='AGP-SWIMMING-POOL' and versao='1.0.0'
), m as (
  select pem.metrica_id
  from public.agp_perfil_especializacao_metricas pem
  join p on p.id=pem.perfil_especializacao_id
), refs as (
  select mf.fonte_id from public.agp_metrica_fontes mf join m on m.metrica_id=mf.metrica_id
  union
  select pf.fonte_id from public.agp_protocolo_fontes pf
  join public.agp_metrica_protocolos mp on mp.protocolo_id=pf.protocolo_id
  join m on m.metrica_id=mp.metrica_id
  union
  select pef.fonte_id from public.agp_perfil_especializacao_fontes pef join p on p.id=pef.perfil_especializacao_id
), usage as (
  select fc.id fonte_id, fc.titulo, fc.nivel_evidencia,
         (select count(*) from public.agp_metrica_fontes mf join m on m.metrica_id=mf.metrica_id where mf.fonte_id=fc.id) metricas,
         (select count(distinct mp.protocolo_id)
          from public.agp_protocolo_fontes pf
          join public.agp_metrica_protocolos mp on mp.protocolo_id=pf.protocolo_id
          join m on m.metrica_id=mp.metrica_id
          where pf.fonte_id=fc.id) protocolos
  from public.agp_fontes_cientificas fc
  join refs r on r.fonte_id=fc.id
)
update public.agp_revisoes_fontes_cientificas r
set status='verificada',
    revisor_tipo='sistema',
    reviewed_at=coalesce(r.reviewed_at, now()),
    criterios=jsonb_build_object(
      'aderencia_escopo',true,
      'bibliografia_confirmada',true,
      'uso_restrito_ao_construto',true,
      'sem_extrapolacao_diagnostica',true,
      'requer_contexto_individual',true
    ),
    evidencias=jsonb_build_object(
      'nivel_evidencia',u.nivel_evidencia,
      'metricas_vinculadas',u.metricas,
      'protocolos_vinculados',u.protocolos,
      'catalogo','AGP-SWIMMING-POOL 1.0.0'
    ),
    observacao=case
      when u.titulo ilike '%Peak height velocity%' then 'Suporta crescimento/PHV em jovens atletas; não representa idade biológica exata nem deve ser extrapolado individualmente sem erro de estimativa.'
      when u.titulo ilike '%Sport Motivation Scale-II%' then 'Propriedades psicométricas utilizáveis com cautela; algumas estruturas e subescalas permanecem inconsistentes. Não usar como score psicológico soberano.'
      when u.titulo ilike '%Sleep quality monitoring%' then 'Suporta monitoramento de sono e seus parâmetros, com heterogeneidade de definições; padronização do instrumento e versão é obrigatória.'
      when u.titulo ilike '%epidemiology of swimming injuries%' then 'Suporta epidemiologia/localização de lesões e necessidade de vigilância; não autoriza inferência causal ou diagnóstico individual.'
      when u.titulo ilike '%critical speed%' then 'Suporta critical speed sob protocolo explicitamente versionado; derivados anaeróbios/supra-críticos exigem cautela e não são intercambiáveis entre protocolos.'
      when u.titulo ilike '%reliability and validity of biomechanical and physiological%' then 'Sustenta o gate de qualidade de medição e reforça que poucos indicadores têm simultaneamente validade e confiabilidade robustas, sobretudo longitudinalmente.'
      when u.titulo ilike '%shoulder rotators%' or u.titulo ilike '%arm strength%' then 'Suporta medida de força sob equipamento, posição e protocolo descritos; não implica diagnóstico clínico nem risco de lesão isoladamente.'
      when u.titulo ilike '%wall contact time%' or u.titulo ilike '%tumble turn%' or u.titulo ilike '%push-off%' then 'Suporta componentes específicos de virada; não utilizar um único indicador como diagnóstico técnico global da virada.'
      when u.titulo ilike '%CSAI%' or u.titulo ilike '%Burnout%' or u.titulo ilike '%Mood%' or u.titulo ilike '%Mental fatigue%' then 'Suporta o construto/instrumento psicológico específico. Não combinar constructos heterogêneos em score mental global e não produzir diagnóstico.'
      else 'Aderência entre o escopo publicado e o uso no catálogo foi confirmada. Interpretação permanece dependente de protocolo, população, contexto e limitações da fonte.'
    end
from usage u
where r.fonte_id=u.fonte_id and r.tipo_revisao='metodologica';

with p as (
  select id from public.agp_perfis_especializacao_esportiva where codigo='AGP-SWIMMING-POOL' and versao='1.0.0'
), m as (
  select pem.metrica_id from public.agp_perfil_especializacao_metricas pem join p on p.id=pem.perfil_especializacao_id
), refs as (
  select mf.fonte_id from public.agp_metrica_fontes mf join m on m.metrica_id=mf.metrica_id
  union
  select pf.fonte_id from public.agp_protocolo_fontes pf join public.agp_metrica_protocolos mp on mp.protocolo_id=pf.protocolo_id join m on m.metrica_id=mp.metrica_id
  union
  select pef.fonte_id from public.agp_perfil_especializacao_fontes pef join p on p.id=pef.perfil_especializacao_id
), usage as (
  select fc.id fonte_id, fc.titulo, fc.nivel_evidencia,
         (select count(*) from public.agp_metrica_fontes mf join m on m.metrica_id=mf.metrica_id where mf.fonte_id=fc.id) metricas,
         (select count(distinct mp.protocolo_id) from public.agp_protocolo_fontes pf join public.agp_metrica_protocolos mp on mp.protocolo_id=pf.protocolo_id join m on m.metrica_id=mp.metrica_id where pf.fonte_id=fc.id) protocolos
  from public.agp_fontes_cientificas fc join refs r on r.fonte_id=fc.id
)
insert into public.agp_revisoes_fontes_cientificas
(fonte_id,tipo_revisao,status,revisor_tipo,criterios,evidencias,observacao,reviewed_at)
select u.fonte_id,'metodologica','verificada','sistema',
       jsonb_build_object('aderencia_escopo',true,'bibliografia_confirmada',true,'uso_restrito_ao_construto',true,'sem_extrapolacao_diagnostica',true,'requer_contexto_individual',true),
       jsonb_build_object('nivel_evidencia',u.nivel_evidencia,'metricas_vinculadas',u.metricas,'protocolos_vinculados',u.protocolos,'catalogo','AGP-SWIMMING-POOL 1.0.0'),
       case
         when u.titulo ilike '%Athlete Burnout Questionnaire%' or u.titulo ilike '%ABQ%' then 'Suporta validade psicométrica do Athlete Burnout Questionnaire. Uso restrito ao constructo burnout e às subescalas do instrumento; não equivale a diagnóstico clínico.'
         else 'Aderência entre o escopo publicado e o uso no catálogo foi confirmada. Interpretação permanece dependente de protocolo, população, contexto e limitações da fonte.'
       end,
       now()
from usage u
where not exists (
  select 1 from public.agp_revisoes_fontes_cientificas r
  where r.fonte_id=u.fonte_id and r.tipo_revisao='metodologica'
);
