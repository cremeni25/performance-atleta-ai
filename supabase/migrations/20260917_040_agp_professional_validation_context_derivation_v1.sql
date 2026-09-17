begin;

alter table public.agp_validacoes_profissionais
  add column if not exists escopo_derivado jsonb not null default '{}'::jsonb,
  add column if not exists contexto_derivado jsonb not null default '{}'::jsonb;

comment on column public.agp_validacoes_profissionais.escopo_derivado is
  'Escopo profissional efetivamente utilizado na validação, resolvido pelo AGP a partir do resultado e da competência do profissional; não é preenchido manualmente pelo usuário.';

comment on column public.agp_validacoes_profissionais.contexto_derivado is
  'Snapshot de contexto resolvido automaticamente pelo AGP (pessoa, participante, projeto e domínios do resultado). Mantido para auditoria sem criar fricção operacional.';

create or replace view public.agp_validacoes_profissionais_canonicas
with (security_invoker = true)
as
select
  v.id,
  v.resultado_id,
  v.decisao,
  v.parecer_tecnico,
  v.competencia_codigo,
  v.credencial_verificada_no_registro,
  v.escopo_derivado,
  v.contexto_derivado,
  v.natureza_validacao,
  v.substitui_resultado_id,
  v.motivo_substituicao,
  v.profissional_auth_id,
  v.created_at
from public.agp_validacoes_profissionais v
where v.natureza_validacao in ('profissional_competencia_canonica','profissional_contexto_derivado');

revoke all on public.agp_validacoes_profissionais_canonicas from public, anon, authenticated;
grant select on public.agp_validacoes_profissionais_canonicas to service_role;

commit;
