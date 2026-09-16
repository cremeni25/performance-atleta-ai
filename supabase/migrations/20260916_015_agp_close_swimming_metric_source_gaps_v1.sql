-- AGP Swimming Pool V1
-- Close the two remaining direct metric->source gaps identified by the live readiness gate.
-- Scientific policy:
-- 1) perceived soreness remains a contextual self-report signal, never a diagnostic result;
-- 2) SWOLF remains optional/contextual and must not be treated as a universal efficiency score.
-- Automated bibliographic/methodological review is documentary consistency checking only;
-- professional validation remains mandatory before scientific publication.

-- 1. Insert the swimmer-specific soreness monitoring source if absent.
insert into public.agp_fontes_cientificas
  (titulo, autores, organizacao, ano, tipo, doi, url, resumo, nivel_evidencia, status_validacao)
select
  'Assessing the Measurement Sensitivity and Diagnostic Characteristics of Athlete-Monitoring Tools in National Swimmers',
  'Crowcroft S; McCleave E; Slattery K; Coutts AJ',
  'International Journal of Sports Physiology and Performance',
  2017,
  'artigo',
  '10.1123/ijspp.2016-0406',
  'https://pubmed.ncbi.nlm.nih.gov/27736255/',
  'Longitudinal swimmer monitoring study including soreness among daily self-report variables. Supports soreness as a monitoring signal but explicitly does not support single-variable diagnosis or deterministic performance inference.',
  'observacional_longitudinal_especifico_natacao',
  'pendente'
where not exists (
  select 1 from public.agp_fontes_cientificas
  where lower(coalesce(doi,'')) = '10.1123/ijspp.2016-0406'
);

-- 2. Insert the peer-reviewed SWOLF source if absent.
insert into public.agp_fontes_cientificas
  (titulo, autores, organizacao, ano, tipo, doi, url, resumo, nivel_evidencia, status_validacao)
select
  'Assessment and Prediction of Swimming Performance Using the SWOLF Index',
  'Madou T; Vanluyten K; Martens J; Iserbyt P',
  'International Journal of Kinesiology in Higher Education',
  2023,
  'artigo',
  '10.1080/24711616.2021.1946452',
  'https://doi.org/10.1080/24711616.2021.1946452',
  'Peer-reviewed study of SWOLF in university students learning front crawl. Supports the formula and limited within-context use, but does not establish universal validity for competitive swimmers, all strokes, pool lengths or longitudinal high-performance inference.',
  'aplicacao_contextual_nao_elite',
  'pendente'
where not exists (
  select 1 from public.agp_fontes_cientificas
  where lower(coalesce(doi,'')) = '10.1080/24711616.2021.1946452'
);

-- 3. Bind soreness to swimmer-specific monitoring evidence.
insert into public.agp_metrica_fontes (metrica_id, fonte_id, justificativa)
select m.id, f.id,
       'Supports perceived soreness as one component of multidimensional longitudinal monitoring in competitive swimmers. Does not justify diagnosis, injury prediction or isolated performance inference.'
from public.agp_metricas_esportivas_canonicas m
join public.agp_fontes_cientificas f
  on lower(coalesce(f.doi,'')) = '10.1123/ijspp.2016-0406'
where m.codigo = 'SWM-REC-005'
on conflict (metrica_id, fonte_id) do nothing;

-- 4. Bind SWOLF to peer-reviewed contextual evidence.
insert into public.agp_metrica_fontes (metrica_id, fonte_id, justificativa)
select m.id, f.id,
       'Supports the SWOLF formula and contextual use. Evidence population was university students learning front crawl; therefore AGP must not treat SWOLF as a universal efficiency, talent, physiology or cross-athlete benchmark.'
from public.agp_metricas_esportivas_canonicas m
join public.agp_fontes_cientificas f
  on lower(coalesce(f.doi,'')) = '10.1080/24711616.2021.1946452'
where m.codigo = 'SWM-OW-006'
on conflict (metrica_id, fonte_id) do nothing;

-- 5. Tighten canonical interpretation boundaries.
update public.agp_metricas_esportivas_canonicas
set limites_interpretacao = 'Autorrelato contextual. Distinguir soreness muscular de dor clínica. Não gera diagnóstico, causalidade, lesão provável ou decisão clínica isoladamente.',
    updated_at = now()
where codigo = 'SWM-REC-005';

update public.agp_metrica_versoes mv
set definicao_cientifica = 'Autorrelato de intensidade/localização de soreness ou dor percebida, registrado em escala e mapa corporal definidos, para compor monitoramento multidimensional.',
    qualidade_evidencia = jsonb_build_object(
      'classe_fonte','Científica - observacional longitudinal em nadadores',
      'fonte_principal','https://pubmed.ncbi.nlm.nih.gov/27736255/',
      'forca_evidencia','Moderada para monitoramento contextual',
      'qualidade_confianca','Moderada',
      'uso_permitido','sinal contextual em conjunto multidimensional'
    ),
    limitacoes = 'Soreness é autorrelato e não discrimina sozinho mudança de performance, diagnóstico, lesão ou causalidade. Dor clínica exige avaliação profissional competente.',
    updated_at = now()
from public.agp_metricas_esportivas_canonicas m
where mv.metrica_id = m.id
  and m.codigo = 'SWM-REC-005'
  and mv.versao = '1.0.0';

update public.agp_metricas_esportivas_canonicas
set limites_interpretacao = 'Métrica derivada contextual. Não possui significado fisiológico universal; não comparar entre piscinas, estilos, protocolos ou atletas sem equivalência estrita. Não usar isoladamente como eficiência, talento ou desempenho.',
    updated_at = now()
where codigo = 'SWM-OW-006';

update public.agp_metrica_versoes mv
set definicao_cientifica = 'Índice derivado pela soma do tempo, em segundos, e da contagem de braçadas para uma distância/protocolo definidos. Pode ser usado como referência intra-atleta em condições equivalentes.',
    qualidade_evidencia = jsonb_build_object(
      'classe_fonte','Científica - aplicação contextual',
      'fonte_principal','https://doi.org/10.1080/24711616.2021.1946452',
      'forca_evidencia','Baixa-Moderada para extrapolação ao alto rendimento',
      'qualidade_confianca','Contextual',
      'uso_permitido','tendência intra-atleta sob protocolo equivalente'
    ),
    aplicabilidade = jsonb_build_object(
      'texto','Opcional; preferencialmente intra-atleta, mesma distância, piscina, estilo, intensidade e convenção de contagem.'
    ),
    limitacoes = 'Estudo de suporte principal foi realizado em universitários aprendendo crawl; generalização para nadadores competitivos, outros estilos e diferentes comprimentos de piscina é limitada. Dispositivos podem introduzir erro na contagem de braçadas/comprimentos. Não usar como score universal de eficiência.',
    obrigatoriedade = 'Opcional',
    updated_at = now()
from public.agp_metricas_esportivas_canonicas m
where mv.metrica_id = m.id
  and m.codigo = 'SWM-OW-006'
  and mv.versao = '1.0.0';

-- 6. Documentary review trail for the two newly referenced sources.
insert into public.agp_revisoes_fontes_cientificas
  (fonte_id, tipo_revisao, status, revisor_tipo, criterios, evidencias, observacao, reviewed_at)
select f.id, 'bibliografica', 'verificada', 'sistema',
       jsonb_build_object('doi_presente',true,'titulo_conferido',true,'escopo_conferido',true),
       jsonb_build_object('doi',f.doi,'url',f.url),
       'Verificação documental automatizada. Não equivale a validação profissional ou peer review adicional pelo AGP.',
       now()
from public.agp_fontes_cientificas f
where lower(coalesce(f.doi,'')) in ('10.1123/ijspp.2016-0406','10.1080/24711616.2021.1946452')
  and not exists (
    select 1 from public.agp_revisoes_fontes_cientificas r
    where r.fonte_id=f.id and r.tipo_revisao='bibliografica' and r.status in ('verificada','aprovada')
  );

insert into public.agp_revisoes_fontes_cientificas
  (fonte_id, tipo_revisao, status, revisor_tipo, criterios, evidencias, observacao, reviewed_at)
select f.id, 'metodologica', 'verificada', 'sistema',
       case
         when lower(coalesce(f.doi,''))='10.1123/ijspp.2016-0406' then
           jsonb_build_object('populacao','nadadores nacionais','desenho','longitudinal observacional','construto','monitoramento incluindo soreness','limite','nenhuma variável isolada discrimina mudança de performance')
         else
           jsonb_build_object('populacao','universitários em aprendizagem de crawl','desenho','intervenção educacional','construto','SWOLF','limite','generalização para alto rendimento e outros contextos não demonstrada')
       end,
       jsonb_build_object('doi',f.doi,'url',f.url),
       'Revisão metodológica automatizada de aderência entre fonte e construto. Uso permanece restrito aos limites registrados e depende de validação profissional para aprovação científica.',
       now()
from public.agp_fontes_cientificas f
where lower(coalesce(f.doi,'')) in ('10.1123/ijspp.2016-0406','10.1080/24711616.2021.1946452')
  and not exists (
    select 1 from public.agp_revisoes_fontes_cientificas r
    where r.fonte_id=f.id and r.tipo_revisao='metodologica' and r.status in ('verificada','aprovada')
  );
