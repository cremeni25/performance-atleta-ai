begin;

alter table public.agp_validacoes_profissionais
  add column if not exists pessoa_id uuid references public.agp_pessoas(id) on delete set null,
  add column if not exists participante_id uuid references public.agp_participantes_projeto(id) on delete set null,
  add column if not exists projeto_id uuid references public.agp_projetos_validacao(id) on delete set null,
  add column if not exists competencia_codigo text references public.agp_competencias_canonicas(codigo) on delete restrict,
  add column if not exists credencial_verificada_no_registro boolean,
  add column if not exists natureza_validacao text not null default 'legado_nao_classificado',
  add column if not exists evidencia_referencia jsonb not null default '[]'::jsonb;

update public.agp_validacoes_profissionais v
set projeto_id = coalesce(v.projeto_id, r.projeto_id)
from public.agp_resultados_analiticos r
where r.id = v.resultado_id
  and v.projeto_id is null;

update public.agp_validacoes_profissionais v
set pessoa_id = pe.pessoa_id,
    participante_id = pp.id
from public.agp_resultados_analiticos r
join public.agp_perfis_esportivos pe on pe.legacy_perfil_atleta_id = r.atleta_id and pe.status = 'ativo'
left join public.agp_participantes_projeto pp
  on pp.pessoa_id = pe.pessoa_id
 and pp.projeto_id = r.projeto_id
 and pp.funcao_no_projeto = 'atleta'
where r.id = v.resultado_id
  and (v.pessoa_id is null or v.participante_id is null);

create index if not exists agp_validacoes_profissionais_participante_idx
  on public.agp_validacoes_profissionais(participante_id, created_at desc);

create index if not exists agp_validacoes_profissionais_competencia_idx
  on public.agp_validacoes_profissionais(competencia_codigo, created_at desc);

create or replace view public.agp_validacoes_profissionais_canonicas
with (security_invoker = true)
as
select
  v.id,
  v.resultado_id,
  v.pessoa_id,
  v.participante_id,
  v.projeto_id,
  v.decisao,
  v.parecer_tecnico,
  v.papel_profissional,
  v.competencia_codigo,
  v.credencial_verificada_no_registro,
  v.natureza_validacao,
  v.evidencia_referencia,
  v.visivel_atleta,
  v.visivel_comissao,
  v.visivel_instituicao,
  v.substitui_resultado_id,
  v.motivo_substituicao,
  v.profissional_auth_id,
  v.created_at
from public.agp_validacoes_profissionais v
where v.natureza_validacao = 'profissional_competencia_canonica';

revoke all on public.agp_validacoes_profissionais_canonicas from public, anon, authenticated;
grant select on public.agp_validacoes_profissionais_canonicas to service_role;

comment on column public.agp_validacoes_profissionais.credencial_verificada_no_registro is
  'Snapshot da condição da credencial profissional no instante da validação. Não deve ser reinterpretado retroativamente.';

comment on column public.agp_validacoes_profissionais.natureza_validacao is
  'Distingue validação profissional canônica por competência de registros legados ou outras naturezas de validação.';

commit;
