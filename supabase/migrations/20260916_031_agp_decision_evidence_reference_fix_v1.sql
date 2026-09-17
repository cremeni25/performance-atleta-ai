-- Fix canonical decision evidence reference identity.
-- A reference may be UUID-backed OR code-backed; it must not require both.

alter table public.agp_decisao_evidencias drop constraint if exists agp_decisao_evidencias_pkey;
alter table public.agp_decisao_evidencias alter column referencia_id drop not null;
alter table public.agp_decisao_evidencias alter column referencia_codigo drop not null;

create unique index if not exists agp_decisao_evidencias_unique_ref_idx
on public.agp_decisao_evidencias(
  decisao_id,
  tipo_evidencia,
  coalesce(referencia_id::text,''),
  coalesce(referencia_codigo,''),
  papel
);

comment on index public.agp_decisao_evidencias_unique_ref_idx is
'Allows either UUID or canonical-code evidence references while preventing duplicate lineage entries.';