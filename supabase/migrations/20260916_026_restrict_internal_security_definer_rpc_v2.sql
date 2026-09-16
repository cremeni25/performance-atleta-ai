-- AGP security hardening v2
-- These SECURITY DEFINER helpers are internal composition functions, not direct client RPCs.
-- Keep execution for postgres/service_role so backend and nested owner-executed helpers continue to work.

revoke execute on function public.agp_consentimento_vigente(uuid,uuid,text) from authenticated;
revoke execute on function public.agp_elegibilidade_operacional(uuid) from authenticated;
revoke execute on function public.agp_instrumentos_ativos_disponiveis(uuid,text,text) from authenticated;
revoke execute on function public.agp_linha_base_vigente(uuid,uuid) from authenticated;
revoke execute on function public.agp_status_onboarding_participante(uuid) from authenticated;

grant execute on function public.agp_consentimento_vigente(uuid,uuid,text) to service_role;
grant execute on function public.agp_elegibilidade_operacional(uuid) to service_role;
grant execute on function public.agp_instrumentos_ativos_disponiveis(uuid,text,text) to service_role;
grant execute on function public.agp_linha_base_vigente(uuid,uuid) to service_role;
grant execute on function public.agp_status_onboarding_participante(uuid) to service_role;
