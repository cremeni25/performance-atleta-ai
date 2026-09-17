-- AGP pre-Point-0 operational SSOT closure v1
-- Scope intentionally limited to the approved technical closure:
-- 1) one canonical source of truth for training/competition;
-- 2) preserve legacy training only as compatibility;
-- 3) retire zero-row duplicate competition structures from migration 033.

-- Never discard operational history silently. If these duplicate structures ever
-- contain data in another environment, reconciliation must occur before removal.
do $$
begin
  if to_regclass('public.agp_participacoes_competicao') is not null
     and exists (select 1 from public.agp_participacoes_competicao limit 1) then
    raise exception 'AGP SSOT closure blocked: agp_participacoes_competicao contains data and requires reconciliation';
  end if;

  if to_regclass('public.agp_parciais_competicao') is not null
     and exists (select 1 from public.agp_parciais_competicao limit 1) then
    raise exception 'AGP SSOT closure blocked: agp_parciais_competicao contains data and requires reconciliation';
  end if;
end $$;

-- This projection pointed to the legacy training table and used a canonical name.
-- The canonical runtime now reads/writes agp_sessoes_esportivas directly.
drop view if exists public.agp_sessoes_treinamento_canonicas;

-- Duplicate competition structures were never populated in production and are no
-- longer part of the Point-0 runtime. Canonical competition remains in
-- agp_participacoes_prova + agp_segmentos_prova.
drop table if exists public.agp_parciais_competicao;
drop table if exists public.agp_participacoes_competicao;

comment on table public.agp_sessoes_treinamento is
'LEGACY COMPATIBILITY ONLY. Not a Point-0 source of truth. Canonical sport sessions live in agp_sessoes_esportivas.';

comment on table public.agp_sessoes_esportivas is
'AGP CANONICAL SSOT for sport sessions/training. Person/project context is derived through participant and longitudinal cycle links.';

comment on table public.agp_participacoes_prova is
'AGP CANONICAL SSOT for competition participation and official result facts.';

comment on table public.agp_segmentos_prova is
'AGP CANONICAL SSOT for swimming race segments/splits linked to agp_participacoes_prova.';

comment on table public.agp_ciclo_sessoes is
'Canonical longitudinal link between sport sessions and day/micro/meso/season/career cycles.';

comment on table public.agp_ciclo_participacoes_prova is
'Canonical longitudinal link between competition participation and longitudinal cycles.';
