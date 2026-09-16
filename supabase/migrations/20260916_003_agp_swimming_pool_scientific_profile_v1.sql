-- AGP Swimming Pool scientific/technical profile foundations v1
-- Additive and evidence-aware. No diagnostic thresholds or global performance score are introduced here.

create table if not exists public.agp_perfil_especializacao_fontes (
  perfil_especializacao_id uuid not null references public.agp_perfis_especializacao_esportiva(id) on delete cascade,
  fonte_id uuid not null references public.agp_fontes_cientificas(id) on delete cascade,
  finalidade text not null,
  created_at timestamptz not null default now(),
  primary key (perfil_especializacao_id, fonte_id)
);

alter table public.agp_perfil_especializacao_fontes enable row level security;

comment on table public.agp_perfil_especializacao_fontes is 'Scientific and regulatory evidence linked to a versioned AGP sport-specialization profile.';

insert into public.agp_fontes_cientificas
  (titulo, autores, organizacao, ano, tipo, doi, url, resumo, nivel_evidencia, status_validacao)
select
  'World Aquatics Competition Regulations - Swimming',
  null,
  'World Aquatics',
  2026,
  'norma',
  null,
  'https://www.worldaquatics.com/news/3090417/competition-regulations',
  'Current official competition-regulation source for swimming. Used for competition structure, technical-rule context and version governance.',
  'normativa_oficial',
  'pendente'
where not exists (
  select 1 from public.agp_fontes_cientificas
  where url='https://www.worldaquatics.com/news/3090417/competition-regulations'
);

insert into public.agp_fontes_cientificas
  (titulo, autores, organizacao, ano, tipo, doi, url, resumo, nivel_evidencia, status_validacao)
select
  'Monitoring the swimmer''s training load: A narrative review of monitoring strategies applied in research',
  'Feijen S; Tate A; Kuppens K; Barry LA; Struyf F',
  'Scandinavian Journal of Medicine & Science in Sports',
  2020,
  'artigo',
  '10.1111/sms.13798',
  'https://pubmed.ncbi.nlm.nih.gov/32767794/',
  'Review of external and internal training-load monitoring strategies in competitive swimming, including volume, heart rate, lactate and perceived exertion.',
  'revisao_narrativa',
  'pendente'
where not exists (
  select 1 from public.agp_fontes_cientificas
  where doi='10.1111/sms.13798'
);

insert into public.agp_fontes_cientificas
  (titulo, autores, organizacao, ano, tipo, doi, url, resumo, nivel_evidencia, status_validacao)
select
  'International survey of training load monitoring practices in competitive swimming: How, what and why not?',
  null,
  'Peer-reviewed competitive swimming practice survey',
  2022,
  'artigo',
  null,
  'https://pubmed.ncbi.nlm.nih.gov/34814022/',
  'International practice survey reporting frequent combined use of internal and external load monitoring, notably swimming volume and session-RPE, and highlighting implementation barriers.',
  'estudo_observacional',
  'pendente'
where not exists (
  select 1 from public.agp_fontes_cientificas
  where url='https://pubmed.ncbi.nlm.nih.gov/34814022/'
);

insert into public.agp_fontes_cientificas
  (titulo, autores, organizacao, ano, tipo, doi, url, resumo, nivel_evidencia, status_validacao)
select
  'Young Swimmers'' Anthropometrics, Biomechanics, Energetics, and Efficiency as Underlying Performance Factors: A Systematic Narrative Review',
  'Morais JE; Barbosa TM; Forte P; Silva AJ; Marinho DA',
  'Frontiers in Physiology',
  2021,
  'artigo',
  null,
  'https://pmc.ncbi.nlm.nih.gov/articles/PMC8481572/',
  'Review supporting a multifactorial, dynamic interpretation of youth swimming performance involving anthropometrics, biomechanics, energetics and efficiency.',
  'revisao_sistematica_narrativa',
  'pendente'
where not exists (
  select 1 from public.agp_fontes_cientificas
  where url='https://pmc.ncbi.nlm.nih.gov/articles/PMC8481572/'
);

insert into public.agp_fontes_cientificas
  (titulo, autores, organizacao, ano, tipo, doi, url, resumo, nivel_evidencia, status_validacao)
select
  'Physical performance determinants in competitive youth swimmers: a systematic review',
  null,
  'Peer-reviewed systematic review',
  2024,
  'artigo',
  null,
  'https://pmc.ncbi.nlm.nih.gov/articles/PMC10797935/',
  'Systematic review identifying strength, power, lean body mass, anaerobic and aerobic measures as relevant determinants in youth competitive swimming, with start and turn performance linked particularly to strength and power.',
  'revisao_sistematica',
  'pendente'
where not exists (
  select 1 from public.agp_fontes_cientificas
  where url='https://pmc.ncbi.nlm.nih.gov/articles/PMC10797935/'
);

update public.agp_perfis_especializacao_esportiva p
set
  ontologia = jsonb_build_object(
    'canonical_language','sport_semantic',
    'sport','swimming',
    'modality','pool',
    'pool_courses',jsonb_build_array('25m','50m'),
    'strokes',jsonb_build_array('freestyle','backstroke','breaststroke','butterfly','individual_medley','relay_medley'),
    'core_concepts',jsonb_build_array(
      'athlete','coach','training_session','competition','event','stroke','distance','pace','split','stroke_rate','stroke_count','distance_per_stroke','start','turn','underwater_phase','finish','readiness','training_load','recovery','intervention','response'
    ),
    'principles',jsonb_build_array(
      'individual_and_team_context_coexist',
      'event_and_stroke_specific_interpretation',
      'no_metric_without_context',
      'no_unvalidated_global_score'
    )
  ),
  estrutura_treino = jsonb_build_object(
    'cycle_levels',jsonb_build_array('day','microcycle','mesocycle','season','longitudinal'),
    'session_types',jsonb_build_array('pool','dryland','strength_conditioning','recovery','competition'),
    'pool_session_dimensions',jsonb_build_array('distance_volume','duration','intensity_context','stroke_distribution','set_structure','rest_interval','pace_target','technical_focus'),
    'technical_components',jsonb_build_array('start','turn','underwater','stroke_mechanics','finish'),
    'rule','planned_and_executed_must_be_distinguishable'
  ),
  estrutura_competitiva = jsonb_build_object(
    'event_based',true,
    'individual_result',true,
    'team_structure',true,
    'courses',jsonb_build_array('25m','50m'),
    'event_dimensions',jsonb_build_array('stroke','distance','course','heat_round','relay_or_individual'),
    'competition_record',jsonb_build_array('official_time','splits','placement','qualification_stage','date','venue','course','event'),
    'rules_source','world_aquatics_current_regulations'
  ),
  posicoes_provas_funcoes = jsonb_build_array(
    jsonb_build_object('type','stroke','values',jsonb_build_array('freestyle','backstroke','breaststroke','butterfly','medley')),
    jsonb_build_object('type','event_profile','values',jsonb_build_array('sprint','middle_distance','distance','relay')),
    jsonb_build_object('type','technical_component','values',jsonb_build_array('start','turn','underwater','finish'))
  ),
  dominios_prioritarios = jsonb_build_array(
    'technical','physiological','physical','recovery','psychological','growth','maturation','contextual','competition'
  ),
  modelo_carga_recuperacao = jsonb_build_object(
    'status','scientific_foundation_v1',
    'external_load',jsonb_build_array('swim_distance','session_duration','set_structure','stroke_distribution','pace_context','dryland_volume'),
    'internal_load',jsonb_build_array('session_rpe','heart_rate_when_available','blood_lactate_when_protocol_appropriate','subjective_wellness'),
    'recovery_context',jsonb_build_array('sleep','fatigue','pain','stress','mood','session_response'),
    'requirements',jsonb_build_array('preserve_pool_and_dryland_context','do_not_interpret_volume_alone','prefer_individual_baseline','record_missingness_and_data_quality'),
    'threshold_policy','no_fixed_universal_threshold_without_protocol_population_and_validation'
  ),
  modelo_desenvolvimento = jsonb_build_object(
    'status','scientific_foundation_v1',
    'youth_multifactorial',true,
    'dimensions',jsonb_build_array('anthropometry','growth','biological_maturation','strength','power','aerobic_capacity','anaerobic_capacity','biomechanics','energetics','efficiency','technical_skill','psychological_context','training_history'),
    'longitudinal_rule','development_must_be_interpreted_against_individual_history_and_maturation_context',
    'category_rule','chronological_category_must_not_replace biological_or_longitudinal_context',
    'talent_rule','no_single_metric_may_define_talent_or_future_performance'
  ),
  regras_contextuais = jsonb_build_object(
    'insufficient_evidence_state','dados_insuficientes',
    'no_unvalidated_global_score',true,
    'separate_fact_inference_hypothesis',true,
    'require_source_and_version_for_scientific_interpretation',true,
    'professional_validation_for_regulated_or_clinical_conclusions',true,
    'event_specificity_required',true,
    'maturation_not_diagnosis',true,
    'competition_rules_versioned',true
  ),
  metadados = coalesce(p.metadados,'{}'::jsonb) || jsonb_build_object(
    'scientific_profile_stage','foundation_v1',
    'scientific_review_required_before_approval',true,
    'last_structural_update','2026-09-16'
  ),
  updated_at = now()
where p.codigo='AGP-SWIMMING-POOL' and p.versao='1.0.0';

insert into public.agp_perfil_especializacao_fontes (perfil_especializacao_id, fonte_id, finalidade)
select p.id, f.id,
  case
    when f.organizacao='World Aquatics' then 'competition_rules_and_swimming_structure'
    when f.doi='10.1111/sms.13798' then 'training_load_monitoring_foundation'
    when f.url='https://pubmed.ncbi.nlm.nih.gov/34814022/' then 'practice_context_for_load_monitoring'
    when f.url='https://pmc.ncbi.nlm.nih.gov/articles/PMC8481572/' then 'youth_multifactorial_development_foundation'
    else 'youth_physical_performance_foundation'
  end
from public.agp_perfis_especializacao_esportiva p
join public.agp_fontes_cientificas f on
  f.url in (
    'https://www.worldaquatics.com/news/3090417/competition-regulations',
    'https://pubmed.ncbi.nlm.nih.gov/32767794/',
    'https://pubmed.ncbi.nlm.nih.gov/34814022/',
    'https://pmc.ncbi.nlm.nih.gov/articles/PMC8481572/',
    'https://pmc.ncbi.nlm.nih.gov/articles/PMC10797935/'
  )
where p.codigo='AGP-SWIMMING-POOL' and p.versao='1.0.0'
on conflict (perfil_especializacao_id, fonte_id) do update set finalidade=excluded.finalidade;
