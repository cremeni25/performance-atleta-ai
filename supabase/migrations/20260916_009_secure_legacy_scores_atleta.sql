-- Close legacy experimental score table to direct client access.
-- Data is preserved for impact analysis; no canonical intelligence may depend on it.

alter table if exists public.scores_atleta enable row level security;

comment on table public.scores_atleta is
  'LEGADO EXPERIMENTAL. RLS enabled; no direct client policies. Preserve for impact analysis only; do not use as canonical scientific intelligence.';
