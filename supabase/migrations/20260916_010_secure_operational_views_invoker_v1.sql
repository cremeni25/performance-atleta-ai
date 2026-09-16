-- Operational views must execute with caller privileges and underlying RLS.

alter view if exists public.agp_status_consentimentos set (security_invoker = true);
alter view if exists public.agp_status_linhas_base set (security_invoker = true);
alter view if exists public.agp_participantes_elegibilidade set (security_invoker = true);
alter view if exists public.agp_elegibilidade_operacional_projeto set (security_invoker = true);
alter view if exists public.agp_catalogo_instrumentos_operacional set (security_invoker = true);
alter view if exists public.agp_coletas_operacionais set (security_invoker = true);
alter view if exists public.agp_execucoes_analiticas_operacionais set (security_invoker = true);
alter view if exists public.agp_resultados_profissionais_operacionais set (security_invoker = true);

revoke all on public.agp_status_consentimentos from anon, authenticated;
revoke all on public.agp_status_linhas_base from anon, authenticated;
revoke all on public.agp_participantes_elegibilidade from anon, authenticated;
revoke all on public.agp_elegibilidade_operacional_projeto from anon, authenticated;
revoke all on public.agp_catalogo_instrumentos_operacional from anon, authenticated;
revoke all on public.agp_coletas_operacionais from anon, authenticated;
revoke all on public.agp_execucoes_analiticas_operacionais from anon, authenticated;
revoke all on public.agp_resultados_profissionais_operacionais from anon, authenticated;

grant select on public.agp_status_consentimentos to authenticated;
grant select on public.agp_status_linhas_base to authenticated;
grant select on public.agp_participantes_elegibilidade to authenticated;
grant select on public.agp_elegibilidade_operacional_projeto to authenticated;
grant select on public.agp_catalogo_instrumentos_operacional to authenticated;
grant select on public.agp_coletas_operacionais to authenticated;
grant select on public.agp_execucoes_analiticas_operacionais to authenticated;
grant select on public.agp_resultados_profissionais_operacionais to authenticated;
