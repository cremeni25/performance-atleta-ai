-- AGP canonical seed: global locales + Swimming / Pool specialization shell
-- This seed is structural and semantic only. It does NOT claim scientific validation.

insert into public.agp_locales (codigo, idioma, pais_codigo, sistema_unidades, timezone_padrao, formatos, ativo)
values
  ('pt-BR','Português (Brasil)','BR','metric','America/Sao_Paulo','{"date":"dd/MM/yyyy","decimal":",","thousands":"."}'::jsonb,true),
  ('en-US','English (United States)','US','mixed','America/New_York','{"date":"MM/dd/yyyy","decimal":".","thousands":","}'::jsonb,true),
  ('es-ES','Español','ES','metric','Europe/Madrid','{"date":"dd/MM/yyyy","decimal":",","thousands":"."}'::jsonb,true)
on conflict (codigo) do update set
  idioma = excluded.idioma,
  pais_codigo = excluded.pais_codigo,
  sistema_unidades = excluded.sistema_unidades,
  timezone_padrao = excluded.timezone_padrao,
  formatos = excluded.formatos,
  ativo = true,
  updated_at = now();

with legacy as (
  select id from public.esportes where slug = 'swimming' limit 1
)
insert into public.agp_esportes_canonicos (codigo,nome_canonico,natureza,contato,legado_esporte_id,ativo)
select 'SWIMMING','Swimming','individual','nao_contato',legacy.id,true from legacy
on conflict (codigo) do update set
  nome_canonico = excluded.nome_canonico,
  natureza = excluded.natureza,
  contato = excluded.contato,
  legado_esporte_id = excluded.legado_esporte_id,
  ativo = true,
  updated_at = now();

with sport as (
  select id from public.agp_esportes_canonicos where codigo='SWIMMING'
), legacy as (
  select m.id
  from public.modalidades m
  join public.esportes e on e.id=m.esporte_id
  where e.slug='swimming' and upper(m.nome)='PISCINA'
  limit 1
)
insert into public.agp_modalidades_canonicas (
  esporte_id,codigo,nome_canonico,tipo_ambiente,estrutura_competitiva,legado_modalidade_id,ativo
)
select sport.id,'POOL','Pool Swimming','aquatic_pool',
  '{"competition_unit":"event","team_context":true,"individual_performance":true}'::jsonb,
  legacy.id,true
from sport cross join legacy
on conflict (esporte_id,codigo) do update set
  nome_canonico = excluded.nome_canonico,
  tipo_ambiente = excluded.tipo_ambiente,
  estrutura_competitiva = excluded.estrutura_competitiva,
  legado_modalidade_id = excluded.legado_modalidade_id,
  ativo = true,
  updated_at = now();

with sport as (
  select id from public.agp_esportes_canonicos where codigo='SWIMMING'
), modality as (
  select m.id from public.agp_modalidades_canonicas m join sport s on s.id=m.esporte_id where m.codigo='POOL'
)
insert into public.agp_perfis_especializacao_esportiva (
  esporte_id,modalidade_id,codigo,versao,status_catalogo,
  ontologia,estrutura_treino,estrutura_competitiva,estrutura_papeis,
  categorias,posicoes_provas_funcoes,dominios_prioritarios,
  modelo_carga_recuperacao,modelo_desenvolvimento,regras_contextuais,integracoes_recomendadas,metadados
)
select sport.id,modality.id,'AGP-SWIMMING-POOL','1.0.0','rascunho',
  '{"canonical_language":"sport_semantic","concepts":["athlete","coach","training_session","competition","event","stroke","distance","pace","split","start","turn","readiness","intervention","response"]}'::jsonb,
  '{"cycle_levels":["day","microcycle","mesocycle","season","longitudinal"],"session_specificity":"swimming_pool"}'::jsonb,
  '{"individual_result":true,"team_structure":true,"event_based":true}'::jsonb,
  '{"technical_team":true,"specialist_professionals":true,"multi_role_person":true}'::jsonb,
  '[]'::jsonb,
  '[]'::jsonb,
  '["technical","physical","physiological","recovery","mental","psychological","growth","maturation","nutritional","contextual"]'::jsonb,
  '{"status":"to_be_scientifically_defined"}'::jsonb,
  '{"status":"to_be_scientifically_defined"}'::jsonb,
  '{"no_unvalidated_global_score":true,"insufficient_evidence_state":"dados_insuficientes"}'::jsonb,
  '[]'::jsonb,
  '{"scientific_status":"not_yet_validated","purpose":"canonical specialization shell","do_not_use_for_scientific_inference":true}'::jsonb
from sport cross join modality
on conflict (codigo,versao) do update set
  esporte_id = excluded.esporte_id,
  modalidade_id = excluded.modalidade_id,
  status_catalogo = 'rascunho',
  ontologia = excluded.ontologia,
  estrutura_treino = excluded.estrutura_treino,
  estrutura_competitiva = excluded.estrutura_competitiva,
  estrutura_papeis = excluded.estrutura_papeis,
  dominios_prioritarios = excluded.dominios_prioritarios,
  modelo_carga_recuperacao = excluded.modelo_carga_recuperacao,
  modelo_desenvolvimento = excluded.modelo_desenvolvimento,
  regras_contextuais = excluded.regras_contextuais,
  metadados = excluded.metadados,
  updated_at = now();

-- Minimal canonical lexicon. These are UI/semantic labels, not scientific claims.
with sport as (
  select id from public.agp_esportes_canonicos where codigo='SWIMMING'
), modality as (
  select m.id from public.agp_modalidades_canonicas m join sport s on s.id=m.esporte_id where m.codigo='POOL'
), terms(conceito_chave,locale_codigo,termo,termo_curto,contexto_uso) as (
  values
    ('sport.name','pt-BR','Natação','Natação','Nome do esporte'),
    ('sport.name','en-US','Swimming','Swimming','Sport name'),
    ('sport.name','es-ES','Natación','Natación','Nombre del deporte'),
    ('modality.name','pt-BR','Natação Piscina','Piscina','Modalidade'),
    ('modality.name','en-US','Pool Swimming','Pool','Modality'),
    ('modality.name','es-ES','Natación en Piscina','Piscina','Modalidad'),
    ('athlete','pt-BR','Atleta','Atleta','Pessoa em acompanhamento esportivo'),
    ('athlete','en-US','Athlete','Athlete','Person under sports monitoring'),
    ('athlete','es-ES','Deportista','Deportista','Persona en seguimiento deportivo'),
    ('coach','pt-BR','Técnico','Técnico','Papel técnico principal'),
    ('coach','en-US','Coach','Coach','Primary technical role'),
    ('coach','es-ES','Entrenador','Entrenador','Rol técnico principal'),
    ('training_session','pt-BR','Sessão de treino','Treino','Sessão operacional de treinamento'),
    ('training_session','en-US','Training session','Training','Operational training session'),
    ('training_session','es-ES','Sesión de entrenamiento','Entrenamiento','Sesión operativa de entrenamiento'),
    ('readiness','pt-BR','Prontidão','Prontidão','Estado diário autorrelatado/contextual'),
    ('readiness','en-US','Readiness','Readiness','Daily self-reported/contextual state'),
    ('readiness','es-ES','Disposición','Disposición','Estado diario autorreportado/contextual')
)
insert into public.agp_lexico_esportivo (
  conceito_chave,locale_codigo,esporte_id,modalidade_id,termo,termo_curto,contexto_uso,ativo
)
select t.conceito_chave,t.locale_codigo,sport.id,modality.id,t.termo,t.termo_curto,t.contexto_uso,true
from terms t cross join sport cross join modality
on conflict (conceito_chave,locale_codigo,esporte_id,modalidade_id) do update set
  termo = excluded.termo,
  termo_curto = excluded.termo_curto,
  contexto_uso = excluded.contexto_uso,
  ativo = true,
  updated_at = now();
