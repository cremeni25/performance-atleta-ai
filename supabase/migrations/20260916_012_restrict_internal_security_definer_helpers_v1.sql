-- Remove direct authenticated RPC access from helpers used only internally/triggers.

revoke execute on function public.agp_calcular_completude_instrumento(uuid,jsonb) from authenticated;
revoke execute on function public.agp_pode_coletar(uuid,uuid) from authenticated;
revoke execute on function public.agp_pode_analisar(uuid,uuid) from authenticated;
revoke execute on function public.agp_project_institution_id(uuid) from authenticated;
