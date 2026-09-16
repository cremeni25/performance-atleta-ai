-- AGP metric-to-protocol relation V1
-- Mirrors production migration 20260916161042.
-- Additive. No public/authenticated policies are created.

create table if not exists public.agp_metrica_protocolos (
  metrica_id uuid not null references public.agp_metricas_esportivas_canonicas(id) on delete cascade,
  protocolo_id uuid not null references public.agp_protocolos(id) on delete restrict,
  papel text not null default 'principal'
    check (papel in ('principal','alternativo','validacao','contextual')),
  obrigatorio boolean not null default false,
  aplicabilidade jsonb not null default '{}'::jsonb,
  observacao text null,
  created_at timestamptz not null default now(),
  primary key (metrica_id, protocolo_id)
);

create index if not exists idx_agp_metrica_protocolos_protocolo
  on public.agp_metrica_protocolos(protocolo_id);

alter table public.agp_metrica_protocolos enable row level security;

comment on table public.agp_metrica_protocolos is
  'Versionable relation between canonical metrics and collection/measurement protocols. A metric may have principal, alternative, validation or contextual protocols.';
