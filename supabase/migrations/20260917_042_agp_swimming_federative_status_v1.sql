-- AGP Swimming: federative status as transversal sport-profile context.
-- This does not determine competition eligibility by itself; it informs professional/institutional context.

alter table public.agp_perfis_esportivos
  add column if not exists status_federativo text not null default 'nao_informado',
  add column if not exists federacao_nome text null,
  add column if not exists registro_federativo text null,
  add column if not exists status_federativo_atualizado_em timestamptz null;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'agp_perfis_esportivos_status_federativo_check'
  ) then
    alter table public.agp_perfis_esportivos
      add constraint agp_perfis_esportivos_status_federativo_check
      check (status_federativo in ('nao_informado','vinculado','federado'));
  end if;
end $$;

comment on column public.agp_perfis_esportivos.status_federativo is
  'Sport registration context. For AGP Swimming M0: nao_informado, vinculado or federado. Contextual field; does not independently prove eligibility for a specific championship.';
comment on column public.agp_perfis_esportivos.federacao_nome is
  'Federation/entity name when applicable. Optional contextual metadata.';
comment on column public.agp_perfis_esportivos.registro_federativo is
  'Federative registration/reference when applicable. Optional and not used as an automatic eligibility decision.';
