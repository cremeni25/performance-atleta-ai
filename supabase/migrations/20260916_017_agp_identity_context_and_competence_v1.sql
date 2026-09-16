-- AGP canonical identity context + competence model
-- Goal: close the canonical sequence identity -> multiple roles -> capabilities -> competencies -> scoped context.
-- No UI is introduced here. This is backend/data foundation for later role-aware workspaces.

create table if not exists public.agp_competencias_canonicas (
  codigo text primary key,
  dominio text not null,
  nome_canonico text not null,
  descricao text not null,
  requer_credencial_regulada boolean not null default false,
  esporte_codigo text null,
  modalidade_codigo text null,
  ativo boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.agp_papel_competencias (
  papel_codigo text not null references public.agp_papeis_canonicos(codigo) on delete cascade,
  competencia_codigo text not null references public.agp_competencias_canonicas(codigo) on delete cascade,
  obrigatoria boolean not null default true,
  escopo jsonb not null default '{}'::jsonb,
  ativo boolean not null default true,
  created_at timestamptz not null default now(),
  primary key (papel_codigo, competencia_codigo)
);

create table if not exists public.agp_credencial_competencias (
  credencial_id uuid not null references public.agp_credenciais_profissionais(id) on delete cascade,
  competencia_codigo text not null references public.agp_competencias_canonicas(codigo) on delete restrict,
  status text not null default 'declarada' check (status in ('declarada','verificada','rejeitada','expirada')),
  evidencia jsonb not null default '{}'::jsonb,
  verificado_por uuid null references auth.users(id),
  verificado_em timestamptz null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (credencial_id, competencia_codigo)
);

insert into public.agp_competencias_canonicas
  (codigo,dominio,nome_canonico,descricao,requer_credencial_regulada,esporte_codigo,modalidade_codigo,ativo)
values
  ('athlete.self_management','athlete','Athlete self-management','Provide authorized self-report and understand own longitudinal returns',false,'SWIMMING','POOL',true),
  ('swimming.coaching','technical','Swimming coaching','Lead swimming technical development in the assigned context',false,'SWIMMING','POOL',true),
  ('swimming.training_design','training','Swimming training design','Plan swimming training according to event, stroke, cycle and athlete context',false,'SWIMMING','POOL',true),
  ('swimming.technical_analysis','technical','Swimming technical analysis','Interpret stroke, start, turn, underwater, pacing and race evidence within protocol limits',false,'SWIMMING','POOL',true),
  ('strength_conditioning','physical','Strength and conditioning','Plan and interpret physical preparation and dry-land evidence',false,null,null,true),
  ('performance.analysis','performance','Performance analysis','Analyze longitudinal performance evidence and competition/training trends',false,null,null,true),
  ('medicine.clinical','medical','Clinical medicine','Interpret and act on medical/clinical evidence within regulated professional scope',true,null,null,true),
  ('physiotherapy.msk_rehab','physiotherapy','Musculoskeletal physiotherapy and rehabilitation','Interpret and act on musculoskeletal and rehabilitation evidence within regulated scope',true,null,null,true),
  ('psychology.sport','psychology','Sport psychology','Interpret and act on psychological evidence within regulated professional scope',true,null,null,true),
  ('nutrition.sport','nutrition','Sports nutrition','Interpret and act on nutritional evidence within regulated professional scope',true,null,null,true),
  ('physiology.exercise','physiology','Exercise physiology','Interpret physiological testing and training-response evidence within professional scope',true,null,null,true),
  ('institution.management','institution','Institution management','Manage institutional people, projects and authorized aggregate intelligence',false,null,null,true),
  ('guardian.support','guardian','Guardian support','Access and support dependent information according to consent and age rules',false,null,null,true),
  ('platform.governance','platform','Platform governance','Govern AGP catalogs, security, scientific versions and platform configuration',false,null,null,true)
on conflict (codigo) do update set
  dominio=excluded.dominio,
  nome_canonico=excluded.nome_canonico,
  descricao=excluded.descricao,
  requer_credencial_regulada=excluded.requer_credencial_regulada,
  esporte_codigo=excluded.esporte_codigo,
  modalidade_codigo=excluded.modalidade_codigo,
  ativo=true,
  updated_at=now();

insert into public.agp_papel_competencias (papel_codigo,competencia_codigo,obrigatoria,escopo,ativo)
values
  ('athlete','athlete.self_management',true,'{}'::jsonb,true),
  ('head_coach','swimming.coaching',true,'{}'::jsonb,true),
  ('head_coach','swimming.training_design',true,'{}'::jsonb,true),
  ('head_coach','swimming.technical_analysis',true,'{}'::jsonb,true),
  ('assistant_coach','swimming.coaching',true,'{"mode":"assisted"}'::jsonb,true),
  ('assistant_coach','swimming.technical_analysis',true,'{"mode":"assisted"}'::jsonb,true),
  ('strength_conditioning_coach','strength_conditioning',true,'{}'::jsonb,true),
  ('performance_analyst','performance.analysis',true,'{}'::jsonb,true),
  ('performance_analyst','swimming.technical_analysis',false,'{"scope":"performance_analysis"}'::jsonb,true),
  ('observer','swimming.technical_analysis',false,'{"mode":"observation_only"}'::jsonb,true),
  ('physician','medicine.clinical',true,'{}'::jsonb,true),
  ('physiotherapist','physiotherapy.msk_rehab',true,'{}'::jsonb,true),
  ('psychologist','psychology.sport',true,'{}'::jsonb,true),
  ('nutritionist','nutrition.sport',true,'{}'::jsonb,true),
  ('physiologist','physiology.exercise',true,'{}'::jsonb,true),
  ('institution_manager','institution.management',true,'{}'::jsonb,true),
  ('guardian','guardian.support',true,'{}'::jsonb,true),
  ('master_governance','platform.governance',true,'{}'::jsonb,true)
on conflict (papel_codigo,competencia_codigo) do update set
  obrigatoria=excluded.obrigatoria,
  escopo=excluded.escopo,
  ativo=true;

alter table public.agp_competencias_canonicas enable row level security;
alter table public.agp_papel_competencias enable row level security;
alter table public.agp_credencial_competencias enable row level security;

revoke all on public.agp_competencias_canonicas from public, anon, authenticated;
revoke all on public.agp_papel_competencias from public, anon, authenticated;
revoke all on public.agp_credencial_competencias from public, anon, authenticated;
grant select, insert, update, delete on public.agp_competencias_canonicas to service_role;
grant select, insert, update, delete on public.agp_papel_competencias to service_role;
grant select, insert, update, delete on public.agp_credencial_competencias to service_role;

create or replace view public.agp_contextos_identidade_efetivos
with (security_invoker = true)
as
select
  e.pessoa_id,
  e.instituicao_id,
  e.projeto_id,
  e.papel_codigo,
  p.familia,
  p.nome_canonico as papel_nome_canonico,
  p.requer_credencial_profissional,
  e.status,
  e.data_inicio,
  e.data_fim,
  e.origem,
  coalesce((
    select jsonb_agg(
      jsonb_build_object(
        'codigo', c.codigo,
        'dominio', c.dominio,
        'natureza', c.natureza,
        'descricao', c.descricao,
        'exige_credencial', c.exige_credencial,
        'escopo', pc.escopo
      ) order by c.codigo
    )
    from public.agp_papel_capacidades pc
    join public.agp_capacidades_canonicas c on c.codigo = pc.capacidade_codigo
    where pc.papel_codigo = e.papel_codigo
      and pc.ativo = true
      and c.ativo = true
  ), '[]'::jsonb) as capacidades,
  coalesce((
    select jsonb_agg(
      jsonb_build_object(
        'codigo', cc.codigo,
        'dominio', cc.dominio,
        'nome', cc.nome_canonico,
        'obrigatoria', pcomp.obrigatoria,
        'requer_credencial_regulada', cc.requer_credencial_regulada,
        'esporte_codigo', cc.esporte_codigo,
        'modalidade_codigo', cc.modalidade_codigo,
        'escopo', pcomp.escopo,
        'credencial_verificada', case
          when cc.requer_credencial_regulada = false then true
          else exists (
            select 1
            from public.agp_credencial_competencias gcc
            join public.agp_credenciais_profissionais gp on gp.id = gcc.credencial_id
            where gp.pessoa_id = e.pessoa_id
              and gp.status = 'validada'
              and (gp.validade is null or gp.validade >= current_date)
              and gcc.competencia_codigo = cc.codigo
              and gcc.status = 'verificada'
          )
        end
      ) order by cc.codigo
    )
    from public.agp_papel_competencias pcomp
    join public.agp_competencias_canonicas cc on cc.codigo = pcomp.competencia_codigo
    where pcomp.papel_codigo = e.papel_codigo
      and pcomp.ativo = true
      and cc.ativo = true
  ), '[]'::jsonb) as competencias
from public.agp_papeis_efetivos_pessoa e
join public.agp_papeis_canonicos p on p.codigo = e.papel_codigo
where e.status = 'ativo'
  and (e.data_fim is null or e.data_fim >= current_date);

revoke all on public.agp_contextos_identidade_efetivos from public, anon, authenticated;
grant select on public.agp_contextos_identidade_efetivos to service_role;

comment on view public.agp_contextos_identidade_efetivos is
'Canonical AGP identity resolver substrate: one person may have multiple simultaneous scoped roles. This view is backend-governed and is not the final UI.';
