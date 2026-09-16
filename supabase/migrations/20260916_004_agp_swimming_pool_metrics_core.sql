-- AGP Swimming Pool canonical metrics core
-- Separates raw observations, derived metrics and interpretation context.
-- Additive and backend-governed; no anon/authenticated policies added here.

create extension if not exists pgcrypto;

create table if not exists public.agp_metricas_esportivas_canonicas (
  id uuid primary key default gen_random_uuid(),
  codigo text not null unique,
  nome_canonico text not null,
  dominio text not null,
  tipo_dado text not null check (tipo_dado in ('bruto','derivado','contextual')),
  unidade_canonica text null,
  origem_preferencial text null,
  formula jsonb not null default '{}'::jsonb,
  requisitos_calculo jsonb not null default '[]'::jsonb,
  regras_qualidade jsonb not null default '{}'::jsonb,
  limites_interpretacao text null,
  ativo boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.agp_perfil_especializacao_metricas (
  perfil_especializacao_id uuid not null references public.agp_perfis_especializacao_esportiva(id) on delete cascade,
  metrica_id uuid not null references public.agp_metricas_esportivas_canonicas(id) on delete restrict,
  prioridade integer not null default 100,
  aplicabilidade jsonb not null default '{}'::jsonb,
  protocolo_minimo jsonb not null default '{}'::jsonb,
  obrigatoriedade text not null default 'contextual' check (obrigatoriedade in ('obrigatoria','recomendada','contextual')),
  created_at timestamptz not null default now(),
  primary key (perfil_especializacao_id, metrica_id)
);

create table if not exists public.agp_metrica_fontes (
  metrica_id uuid not null references public.agp_metricas_esportivas_canonicas(id) on delete cascade,
  fonte_id uuid not null references public.agp_fontes_cientificas(id) on delete cascade,
  justificativa text null,
  created_at timestamptz not null default now(),
  primary key (metrica_id, fonte_id)
);

alter table public.agp_metricas_esportivas_canonicas enable row level security;
alter table public.agp_perfil_especializacao_metricas enable row level security;
alter table public.agp_metrica_fontes enable row level security;

comment on table public.agp_metricas_esportivas_canonicas is 'Canonical sport metrics with explicit raw/derived/contextual semantics.';
comment on table public.agp_perfil_especializacao_metricas is 'Binds versioned Sport Profiles to canonical metrics and protocol requirements.';
comment on table public.agp_metrica_fontes is 'Scientific provenance for each canonical metric.';

insert into public.agp_metricas_esportivas_canonicas
(codigo,nome_canonico,dominio,tipo_dado,unidade_canonica,origem_preferencial,formula,requisitos_calculo,regras_qualidade,limites_interpretacao)
values
('SWIM_EVENT_TIME','Event time','performance','bruto','s','official_timing_or_validated_manual','{}','[]','{"timestamp_required":true,"distance_required":true,"stroke_required":true}','Interpret only in event, pool length, stroke, age/category and competition context.'),
('SWIM_SPLIT_TIME','Split time','performance','bruto','s','official_timing_or_validated_manual','{}','[]','{"split_distance_required":true}','Do not compare splits across different split distances without normalization.'),
('SWIM_DISTANCE','Swum distance','training_load','bruto','m','session_log','{}','[]','{"pool_length_required":true}','Volume alone is not a performance interpretation.'),
('SWIM_DURATION','Session duration','training_load','bruto','s','session_log','{}','[]','{}','Separate pool session duration from dry-land duration.'),
('SWIM_STROKE_COUNT','Stroke count','biomechanics','bruto','count','validated_manual_or_sensor','{}','[]','{"segment_distance_required":true,"stroke_definition_required":true}','Counting convention must be explicit and consistent.'),
('SWIM_STROKE_RATE','Stroke rate','biomechanics','bruto','cycles/min','validated_manual_or_sensor','{}','[]','{"stroke_required":true,"measurement_window_required":true}','Interpret jointly with speed, distance/event, stroke and athlete baseline.'),
('SWIM_SPEED','Swimming speed','performance','derivado','m/s','calculated','{"expression":"distance_m / time_s"}','["distance_m","time_s"]','{"time_gt_zero":true}','Use only when distance and timing boundaries are valid.'),
('SWIM_DISTANCE_PER_CYCLE','Distance per stroke cycle','biomechanics','derivado','m/cycle','calculated','{"expression":"speed_m_s * 60 / stroke_rate_cycles_min"}','["speed_m_s","stroke_rate_cycles_min"]','{"stroke_rate_gt_zero":true}','Do not interpret higher values as universally better; depends on event, stroke, speed and athlete.'),
('SWIM_START_TIME','Start segment time','biomechanics','bruto','s','validated_video_or_timing_system','{}','[]','{"protocol_boundary_required":true}','Boundary definition must be fixed by protocol before longitudinal comparison.'),
('SWIM_TURN_TIME','Turn segment time','biomechanics','bruto','s','validated_video_or_timing_system','{}','[]','{"protocol_boundary_required":true}','Boundary definition must be fixed by protocol before longitudinal comparison.'),
('SWIM_UNDERWATER_DISTANCE','Underwater distance','biomechanics','bruto','m','validated_video_or_sensor','{}','[]','{"event_and_stroke_required":true}','Must be interpreted under current competition rules and event/stroke context.'),
('SWIM_UNDERWATER_TIME','Underwater time','biomechanics','bruto','s','validated_video_or_sensor','{}','[]','{"event_and_stroke_required":true}','Not a universal quality metric; depends on speed, event and legal constraints.'),
('SWIM_SESSION_RPE','Session perceived exertion','internal_load','bruto','0-10','athlete_self_report','{}','[]','{"scale_version_required":true}','Subjective internal-load signal; should not be treated as objective external load.'),
('SWIM_SESSION_LOAD_SRPE','Session load by sRPE','internal_load','derivado','AU','calculated','{"expression":"session_duration_min * session_rpe"}','["session_duration_min","session_rpe"]','{"same_scale_required":true}','Useful for longitudinal internal-load tracking; not a universal threshold for readiness or risk.'),
('SWIM_PACE','Pace','performance','derivado','s/100m','calculated','{"expression":"time_s / distance_m * 100"}','["distance_m","time_s"]','{"distance_gt_zero":true}','Compare only under compatible stroke, pool and task context.'),
('SWIM_PLANNED_EXECUTED_VOLUME_DELTA','Planned-executed volume delta','training_process','derivado','m','calculated','{"expression":"executed_volume_m - planned_volume_m"}','["planned_volume_m","executed_volume_m"]','{}','Deviation requires context; it is not intrinsically positive or negative.')
on conflict (codigo) do update set
  nome_canonico=excluded.nome_canonico,
  dominio=excluded.dominio,
  tipo_dado=excluded.tipo_dado,
  unidade_canonica=excluded.unidade_canonica,
  origem_preferencial=excluded.origem_preferencial,
  formula=excluded.formula,
  requisitos_calculo=excluded.requisitos_calculo,
  regras_qualidade=excluded.regras_qualidade,
  limites_interpretacao=excluded.limites_interpretacao,
  updated_at=now();

do $$
declare
  p uuid;
begin
  select id into p from public.agp_perfis_especializacao_esportiva
  where codigo='AGP-SWIMMING-POOL' and versao='1.0.0' limit 1;
  if p is not null then
    insert into public.agp_perfil_especializacao_metricas
    (perfil_especializacao_id,metrica_id,prioridade,aplicabilidade,protocolo_minimo,obrigatoriedade)
    select p,m.id,
      case m.codigo
        when 'SWIM_EVENT_TIME' then 10
        when 'SWIM_SPLIT_TIME' then 20
        when 'SWIM_DISTANCE' then 30
        when 'SWIM_SESSION_RPE' then 40
        when 'SWIM_STROKE_RATE' then 50
        else 100 end,
      '{"sport":"swimming","modality":"pool"}'::jsonb,
      case
        when m.codigo in ('SWIM_START_TIME','SWIM_TURN_TIME') then '{"fixed_segment_boundaries":true}'::jsonb
        when m.codigo in ('SWIM_STROKE_RATE','SWIM_STROKE_COUNT','SWIM_DISTANCE_PER_CYCLE') then '{"stroke_and_segment_context":true}'::jsonb
        else '{}'::jsonb end,
      case
        when m.codigo in ('SWIM_EVENT_TIME','SWIM_DISTANCE') then 'recomendada'
        else 'contextual' end
    from public.agp_metricas_esportivas_canonicas m
    where m.codigo like 'SWIM_%'
    on conflict (perfil_especializacao_id,metrica_id) do update set
      prioridade=excluded.prioridade,
      aplicabilidade=excluded.aplicabilidade,
      protocolo_minimo=excluded.protocolo_minimo,
      obrigatoriedade=excluded.obrigatoriedade;
  end if;
end $$;

-- Add additional scientific sources only if not already catalogued.
insert into public.agp_fontes_cientificas (titulo,autores,organizacao,ano,tipo,doi,url,resumo,nivel_evidencia,status_validacao)
select 'Energetics and biomechanics as determining factors of swimming performance: updating the state of the art',
       'Barbosa TM; Bragada JA; Reis VM; Marinho DA; Carvalho C; Silva AJ',
       null,2010,'artigo','10.1016/j.jsams.2009.01.003','https://pubmed.ncbi.nlm.nih.gov/19409842/',
       'Review of energetic and biomechanical determinants, including stroke length, stroke frequency and swimming velocity.',
       'review','pendente'
where not exists (select 1 from public.agp_fontes_cientificas where doi='10.1016/j.jsams.2009.01.003');

insert into public.agp_fontes_cientificas (titulo,autores,organizacao,ano,tipo,doi,url,resumo,nivel_evidencia,status_validacao)
select 'Coordination and stroking parameters in the four swimming techniques: a narrative review',
       null,null,2021,'artigo','10.1080/14763141.2021.1959945','https://pubmed.ncbi.nlm.nih.gov/34372755/',
       'Review of stroke rate, stroke length, stroke index, propelling efficiency and inter-limb coordination across swimming techniques.',
       'review','pendente'
where not exists (select 1 from public.agp_fontes_cientificas where doi='10.1080/14763141.2021.1959945');

insert into public.agp_fontes_cientificas (titulo,autores,organizacao,ano,tipo,doi,url,resumo,nivel_evidencia,status_validacao)
select 'Swimming biomechanics: from the pool to the lab … and back.',
       null,null,2023,'artigo',null,'https://pubmed.ncbi.nlm.nih.gov/37503541/',
       'Integrative perspective on swimming economy, velocity variation, propulsion, drag and internal load for coaching practice.',
       'expert_review','pendente'
where not exists (select 1 from public.agp_fontes_cientificas where url='https://pubmed.ncbi.nlm.nih.gov/37503541/');

-- Link relevant sources to the metric catalogue without claiming final validation.
insert into public.agp_metrica_fontes (metrica_id,fonte_id,justificativa)
select m.id,f.id,'Supports biomechanical context and the joint interpretation of swimming velocity, stroke rate and stroke length/distance per cycle.'
from public.agp_metricas_esportivas_canonicas m
join public.agp_fontes_cientificas f on f.doi='10.1016/j.jsams.2009.01.003'
where m.codigo in ('SWIM_SPEED','SWIM_STROKE_RATE','SWIM_DISTANCE_PER_CYCLE')
on conflict do nothing;

insert into public.agp_metrica_fontes (metrica_id,fonte_id,justificativa)
select m.id,f.id,'Supports stroke-parameter and coordination context; metrics are not interpreted in isolation.'
from public.agp_metricas_esportivas_canonicas m
join public.agp_fontes_cientificas f on f.doi='10.1080/14763141.2021.1959945'
where m.codigo in ('SWIM_STROKE_RATE','SWIM_STROKE_COUNT','SWIM_DISTANCE_PER_CYCLE')
on conflict do nothing;

insert into public.agp_metrica_fontes (metrica_id,fonte_id,justificativa)
select m.id,f.id,'Supports integrative biomechanical and internal-load interpretation for daily coaching use.'
from public.agp_metricas_esportivas_canonicas m
join public.agp_fontes_cientificas f on f.url='https://pubmed.ncbi.nlm.nih.gov/37503541/'
where m.codigo in ('SWIM_SPEED','SWIM_SESSION_RPE','SWIM_START_TIME','SWIM_TURN_TIME','SWIM_UNDERWATER_TIME','SWIM_UNDERWATER_DISTANCE')
on conflict do nothing;
