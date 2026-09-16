-- AGP scientific-source review trail V1
-- Separates system bibliographic verification from methodological/professional validation.

create table if not exists public.agp_revisoes_fontes_cientificas (
  id uuid primary key default gen_random_uuid(),
  fonte_id uuid not null references public.agp_fontes_cientificas(id) on delete cascade,
  tipo_revisao text not null check (tipo_revisao in ('bibliografica','metodologica','profissional')),
  status text not null check (status in ('pendente','verificada','aprovada','rejeitada','obsoleta')),
  revisor_tipo text not null check (revisor_tipo in ('sistema','profissional')),
  criterios jsonb not null default '{}'::jsonb,
  evidencias jsonb not null default '{}'::jsonb,
  observacao text null,
  created_at timestamptz not null default now(),
  reviewed_at timestamptz null
);

create index if not exists idx_agp_revisoes_fontes_fonte
  on public.agp_revisoes_fontes_cientificas(fonte_id);
create index if not exists idx_agp_revisoes_fontes_status
  on public.agp_revisoes_fontes_cientificas(tipo_revisao,status);

alter table public.agp_revisoes_fontes_cientificas enable row level security;

comment on table public.agp_revisoes_fontes_cientificas is
  'Review trail separating bibliographic verification from methodological and professional validation of scientific sources.';
