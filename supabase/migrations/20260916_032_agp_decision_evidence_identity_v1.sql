-- Give each decision-evidence lineage record a stable canonical identity.

alter table public.agp_decisao_evidencias
  add column if not exists id uuid default gen_random_uuid();

update public.agp_decisao_evidencias
set id = gen_random_uuid()
where id is null;

alter table public.agp_decisao_evidencias alter column id set not null;
alter table public.agp_decisao_evidencias add constraint agp_decisao_evidencias_id_key unique (id);

comment on column public.agp_decisao_evidencias.id is
'Stable identity for one evidence-lineage edge supporting a canonical decision.';