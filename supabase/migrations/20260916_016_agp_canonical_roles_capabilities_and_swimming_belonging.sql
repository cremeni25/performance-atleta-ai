-- AGP canonical roles, capabilities and Swimming belonging semantics
-- Goal: preserve one identity with multiple roles/scopes and make Swimming feel native from end to end.
-- Additive only. Legacy role text is preserved and bridged to canonical codes.

create table if not exists public.agp_papeis_canonicos (
  codigo text primary key,
  familia text not null check (familia in ('atleta','equipe_tecnica','especialista','gestao','governanca','responsavel')),
  nome_canonico text not null,
  requer_credencial_profissional boolean not null default false,
  escopo_padrao jsonb not null default '{}'::jsonb,
  ativo boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.agp_capacidades_canonicas (
  codigo text primary key,
  dominio text not null,
  natureza text not null check (natureza in ('visualizar','registrar','validar','decidir','administrar')),
  descricao text not null,
  exige_credencial boolean not null default false,
  ativo boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.agp_papel_capacidades (
  papel_codigo text not null references public.agp_papeis_canonicos(codigo) on delete cascade,
  capacidade_codigo text not null references public.agp_capacidades_canonicas(codigo) on delete cascade,
  escopo jsonb not null default '{}'::jsonb,
  ativo boolean not null default true,
  created_at timestamptz not null default now(),
  primary key (papel_codigo, capacidade_codigo)
);

insert into public.agp_papeis_canonicos (codigo,familia,nome_canonico,requer_credencial_profissional,escopo_padrao,ativo)
values
  ('athlete','atleta','Athlete',false,'{"own_data":true,"own_history":true}'::jsonb,true),
  ('head_coach','equipe_tecnica','Head Coach',false,'{"team_scope":true,"assigned_athletes":true}'::jsonb,true),
  ('assistant_coach','equipe_tecnica','Assistant Coach',false,'{"team_scope":true,"assigned_athletes":true}'::jsonb,true),
  ('strength_conditioning_coach','equipe_tecnica','Strength & Conditioning Coach',false,'{"assigned_athletes":true,"dry_land":true}'::jsonb,true),
  ('performance_analyst','equipe_tecnica','Performance Analyst',false,'{"assigned_athletes":true,"performance_analysis":true}'::jsonb,true),
  ('observer','equipe_tecnica','Observer',false,'{"assigned_athletes":true,"observation_only":true}'::jsonb,true),
  ('physician','especialista','Physician',true,'{"clinical_scope":true}'::jsonb,true),
  ('physiotherapist','especialista','Physiotherapist',true,'{"musculoskeletal_scope":true,"rehab_scope":true}'::jsonb,true),
  ('psychologist','especialista','Psychologist',true,'{"psychological_scope":true}'::jsonb,true),
  ('nutritionist','especialista','Nutritionist',true,'{"nutrition_scope":true}'::jsonb,true),
  ('physiologist','especialista','Physiologist',true,'{"physiology_scope":true}'::jsonb,true),
  ('institution_manager','gestao','Institution Manager',false,'{"institution_scope":true}'::jsonb,true),
  ('guardian','responsavel','Guardian',false,'{"dependent_scope":true}'::jsonb,true),
  ('master_governance','governanca','AGP Master Governance',false,'{"platform_governance":true,"not_routine_operator":true}'::jsonb,true)
on conflict (codigo) do update set
  familia=excluded.familia,
  nome_canonico=excluded.nome_canonico,
  requer_credencial_profissional=excluded.requer_credencial_profissional,
  escopo_padrao=excluded.escopo_padrao,
  ativo=true,
  updated_at=now();

insert into public.agp_capacidades_canonicas (codigo,dominio,natureza,descricao,exige_credencial,ativo)
values
  ('own.read','identity','visualizar','Read own longitudinal profile and authorized returns',false,true),
  ('self_report.write','evidence','registrar','Submit self-reported readiness and contextual evidence',false,true),
  ('training.plan','training','decidir','Plan training for assigned athletes',false,true),
  ('training.record','training','registrar','Record or confirm training execution',false,true),
  ('competition.record','competition','registrar','Record competition/event evidence',false,true),
  ('evidence.review_technical','evidence','validar','Review technical evidence within assigned sport scope',false,true),
  ('decision.technical','decision','decidir','Make technical decisions within assigned sport scope',false,true),
  ('intervention.technical','intervention','decidir','Create and follow technical interventions',false,true),
  ('analysis.performance','performance','validar','Analyze performance evidence and contextual trends',false,true),
  ('assessment.physical','physical','validar','Assess physical / strength-conditioning evidence',false,true),
  ('assessment.medical','medical','validar','Assess clinical/medical evidence within credentialed scope',true,true),
  ('assessment.physiotherapy','physiotherapy','validar','Assess musculoskeletal and rehabilitation evidence within credentialed scope',true,true),
  ('assessment.psychology','psychology','validar','Assess psychological evidence within credentialed scope',true,true),
  ('assessment.nutrition','nutrition','validar','Assess nutritional evidence within credentialed scope',true,true),
  ('assessment.physiology','physiology','validar','Assess physiological evidence within credentialed scope',true,true),
  ('institution.people_manage','institution','administrar','Manage institutional people and role assignments',false,true),
  ('institution.project_manage','institution','administrar','Manage institutional projects and operational context',false,true),
  ('institution.aggregate_read','institution','visualizar','Read authorized aggregated institutional intelligence',false,true),
  ('guardian.dependent_read','identity','visualizar','Read authorized dependent information according to consent and age rules',false,true),
  ('platform.govern','platform','administrar','Govern platform catalogs, security and system configuration without replacing operational professionals',false,true)
on conflict (codigo) do update set
  dominio=excluded.dominio,
  natureza=excluded.natureza,
  descricao=excluded.descricao,
  exige_credencial=excluded.exige_credencial,
  ativo=true,
  updated_at=now();

insert into public.agp_papel_capacidades (papel_codigo,capacidade_codigo,escopo,ativo)
values
  ('athlete','own.read','{}'::jsonb,true),
  ('athlete','self_report.write','{}'::jsonb,true),
  ('athlete','training.record','{"mode":"confirm_or_self_record_when_authorized"}'::jsonb,true),
  ('head_coach','training.plan','{}'::jsonb,true),
  ('head_coach','training.record','{}'::jsonb,true),
  ('head_coach','competition.record','{}'::jsonb,true),
  ('head_coach','evidence.review_technical','{}'::jsonb,true),
  ('head_coach','decision.technical','{}'::jsonb,true),
  ('head_coach','intervention.technical','{}'::jsonb,true),
  ('assistant_coach','training.record','{}'::jsonb,true),
  ('assistant_coach','competition.record','{}'::jsonb,true),
  ('assistant_coach','evidence.review_technical','{}'::jsonb,true),
  ('strength_conditioning_coach','training.plan','{"scope":"dry_land"}'::jsonb,true),
  ('strength_conditioning_coach','training.record','{"scope":"dry_land"}'::jsonb,true),
  ('strength_conditioning_coach','assessment.physical','{}'::jsonb,true),
  ('performance_analyst','analysis.performance','{}'::jsonb,true),
  ('performance_analyst','competition.record','{}'::jsonb,true),
  ('performance_analyst','evidence.review_technical','{"scope":"performance_analysis"}'::jsonb,true),
  ('observer','competition.record','{"mode":"observation_only"}'::jsonb,true),
  ('physician','assessment.medical','{}'::jsonb,true),
  ('physiotherapist','assessment.physiotherapy','{}'::jsonb,true),
  ('psychologist','assessment.psychology','{}'::jsonb,true),
  ('nutritionist','assessment.nutrition','{}'::jsonb,true),
  ('physiologist','assessment.physiology','{}'::jsonb,true),
  ('institution_manager','institution.people_manage','{}'::jsonb,true),
  ('institution_manager','institution.project_manage','{}'::jsonb,true),
  ('institution_manager','institution.aggregate_read','{}'::jsonb,true),
  ('guardian','guardian.dependent_read','{}'::jsonb,true),
  ('master_governance','platform.govern','{}'::jsonb,true)
on conflict (papel_codigo,capacidade_codigo) do update set
  escopo=excluded.escopo,
  ativo=true;

alter table public.agp_papeis_institucionais
  add column if not exists papel_codigo text null references public.agp_papeis_canonicos(codigo) on delete restrict;

alter table public.agp_participantes_projeto
  add column if not exists funcao_canonica_codigo text null references public.agp_papeis_canonicos(codigo) on delete restrict;

update public.agp_papeis_institucionais
set papel_codigo = case papel
  when 'atleta' then 'athlete'
  when 'tecnico' then 'head_coach'
  when 'treinador' then 'head_coach'
  when 'preparador_fisico' then 'strength_conditioning_coach'
  when 'medico' then 'physician'
  when 'fisioterapeuta' then 'physiotherapist'
  when 'psicologo' then 'psychologist'
  when 'nutricionista' then 'nutritionist'
  when 'gestor' then 'institution_manager'
  when 'analista' then 'performance_analyst'
  when 'responsavel_legal' then 'guardian'
  else papel_codigo
end
where papel_codigo is null;

update public.agp_participantes_projeto
set funcao_canonica_codigo = case funcao_no_projeto
  when 'atleta' then 'athlete'
  when 'tecnico' then 'head_coach'
  when 'treinador' then 'head_coach'
  when 'preparador_fisico' then 'strength_conditioning_coach'
  when 'medico' then 'physician'
  when 'fisioterapeuta' then 'physiotherapist'
  when 'psicologo' then 'psychologist'
  when 'nutricionista' then 'nutritionist'
  when 'gestor' then 'institution_manager'
  when 'analista' then 'performance_analyst'
  when 'responsavel_legal' then 'guardian'
  else funcao_canonica_codigo
end
where funcao_canonica_codigo is null;

create index if not exists agp_papeis_institucionais_papel_codigo_idx
  on public.agp_papeis_institucionais(papel_codigo);
create index if not exists agp_participantes_projeto_funcao_canonica_idx
  on public.agp_participantes_projeto(funcao_canonica_codigo);

-- Swimming-specific belonging vocabulary: same canonical concept, native sport language.
with sport as (
  select id from public.agp_esportes_canonicos where codigo='SWIMMING'
), modality as (
  select m.id from public.agp_modalidades_canonicas m join sport s on s.id=m.esporte_id where m.codigo='POOL'
), terms(conceito_chave,locale_codigo,termo,termo_curto,contexto_uso) as (
  values
    ('athlete','pt-BR','Nadador','Nadador','Identidade esportiva visível na Natação Piscina'),
    ('athlete','en-US','Swimmer','Swimmer','Visible sport identity in Pool Swimming'),
    ('athlete','es-ES','Nadador','Nadador','Identidad deportiva visible en Natación en Piscina'),
    ('role.head_coach','pt-BR','Técnico de Natação','Técnico','Papel técnico principal da equipe de natação'),
    ('role.head_coach','en-US','Head Swim Coach','Head Coach','Primary technical role in the swim team'),
    ('role.head_coach','es-ES','Entrenador principal de natación','Entrenador','Rol técnico principal del equipo de natación'),
    ('role.assistant_coach','pt-BR','Técnico Assistente de Natação','Assistente','Equipe técnica de natação'),
    ('role.assistant_coach','en-US','Assistant Swim Coach','Assistant Coach','Swimming technical team'),
    ('role.assistant_coach','es-ES','Entrenador asistente de natación','Asistente','Equipo técnico de natación'),
    ('role.strength_conditioning_coach','pt-BR','Preparador Físico','Preparador Físico','Força, potência e treino seco'),
    ('role.strength_conditioning_coach','en-US','Strength & Conditioning Coach','S&C Coach','Strength, power and dry-land training'),
    ('role.strength_conditioning_coach','es-ES','Preparador físico','Preparador físico','Fuerza, potencia y trabajo en seco'),
    ('role.performance_analyst','pt-BR','Analista de Performance','Analista','Análise técnica e de performance da natação'),
    ('role.performance_analyst','en-US','Performance Analyst','Analyst','Swimming technical and performance analysis'),
    ('role.performance_analyst','es-ES','Analista de rendimiento','Analista','Análisis técnico y de rendimiento en natación'),
    ('role.physician','pt-BR','Médico','Médico','Escopo clínico autorizado'),
    ('role.physician','en-US','Physician','Physician','Authorized clinical scope'),
    ('role.physician','es-ES','Médico','Médico','Ámbito clínico autorizado'),
    ('role.physiotherapist','pt-BR','Fisioterapeuta','Fisioterapeuta','Saúde musculoesquelética e reabilitação'),
    ('role.physiotherapist','en-US','Physiotherapist','Physio','Musculoskeletal health and rehabilitation'),
    ('role.physiotherapist','es-ES','Fisioterapeuta','Fisioterapeuta','Salud musculoesquelética y rehabilitación'),
    ('role.psychologist','pt-BR','Psicólogo do Esporte','Psicólogo','Psicologia do esporte e performance'),
    ('role.psychologist','en-US','Sport Psychologist','Psychologist','Sport and performance psychology'),
    ('role.psychologist','es-ES','Psicólogo deportivo','Psicólogo','Psicología deportiva y del rendimiento'),
    ('role.nutritionist','pt-BR','Nutricionista Esportivo','Nutricionista','Nutrição esportiva'),
    ('role.nutritionist','en-US','Sports Nutritionist','Nutritionist','Sports nutrition'),
    ('role.nutritionist','es-ES','Nutricionista deportivo','Nutricionista','Nutrición deportiva'),
    ('role.physiologist','pt-BR','Fisiologista','Fisiologista','Fisiologia do exercício e performance'),
    ('role.physiologist','en-US','Exercise Physiologist','Physiologist','Exercise physiology and performance'),
    ('role.physiologist','es-ES','Fisiólogo del ejercicio','Fisiólogo','Fisiología del ejercicio y rendimiento'),
    ('workspace.today','pt-BR','Hoje na Natação','Hoje','Entrada diária contextual do AGP Swimming Intelligence'),
    ('workspace.today','en-US','Today in Swimming','Today','Daily contextual entry for AGP Swimming Intelligence'),
    ('workspace.today','es-ES','Hoy en Natación','Hoy','Entrada diaria contextual de AGP Swimming Intelligence'),
    ('workspace.next_action','pt-BR','Próxima ação','Próxima ação','Ação justificável seguinte no contexto longitudinal'),
    ('workspace.next_action','en-US','Next action','Next action','Next justified action in the longitudinal context'),
    ('workspace.next_action','es-ES','Próxima acción','Próxima acción','Siguiente acción justificable en el contexto longitudinal')
)
insert into public.agp_lexico_esportivo (
  conceito_chave,locale_codigo,esporte_id,modalidade_id,termo,termo_curto,contexto_uso,ativo
)
select t.conceito_chave,t.locale_codigo,sport.id,modality.id,t.termo,t.termo_curto,t.contexto_uso,true
from terms t cross join sport cross join modality
on conflict (conceito_chave,locale_codigo,esporte_id,modalidade_id) do update set
  termo=excluded.termo,
  termo_curto=excluded.termo_curto,
  contexto_uso=excluded.contexto_uso,
  ativo=true,
  updated_at=now();

create or replace view public.agp_papeis_efetivos_pessoa
with (security_invoker = true)
as
select
  pi.pessoa_id,
  pi.instituicao_id,
  null::uuid as projeto_id,
  pi.papel_codigo,
  pc.familia,
  pi.status,
  pi.data_inicio,
  pi.data_fim,
  'instituicao'::text as origem
from public.agp_papeis_institucionais pi
join public.agp_papeis_canonicos pc on pc.codigo=pi.papel_codigo
where pi.papel_codigo is not null
union all
select
  pp.pessoa_id,
  pv.instituicao_id,
  pp.projeto_id,
  pp.funcao_canonica_codigo as papel_codigo,
  pc.familia,
  case when pp.ativo then 'ativo' else 'encerrado' end as status,
  pp.data_inicio,
  pp.data_fim,
  'projeto'::text as origem
from public.agp_participantes_projeto pp
join public.agp_projetos_validacao pv on pv.id=pp.projeto_id
join public.agp_papeis_canonicos pc on pc.codigo=pp.funcao_canonica_codigo
where pp.funcao_canonica_codigo is not null;

alter table public.agp_papeis_canonicos enable row level security;
alter table public.agp_capacidades_canonicas enable row level security;
alter table public.agp_papel_capacidades enable row level security;

revoke all on public.agp_papeis_efetivos_pessoa from public, anon, authenticated;
grant select on public.agp_papeis_efetivos_pessoa to service_role;

comment on table public.agp_papeis_canonicos is 'Canonical multi-role taxonomy. One person may hold multiple roles simultaneously across institution/project scopes.';
comment on table public.agp_capacidades_canonicas is 'Canonical capabilities used to derive access by role + scope + professional competence.';
comment on table public.agp_papel_capacidades is 'Default role-to-capability mapping; final authorization must also consider scope, project and credentials.';
comment on view public.agp_papeis_efetivos_pessoa is 'Canonical effective role projection bridging current institution/project assignments without replacing legacy text.';
