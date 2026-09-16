-- SECURITY DEFINER functions must never be executable anonymously.
-- Trigger-only helpers also have direct authenticated EXECUTE removed.

revoke execute on function public.agp_aplicar_validacao_profissional() from public, anon, authenticated;
revoke execute on function public.agp_assert_consentimento_coleta() from public, anon, authenticated;
revoke execute on function public.agp_assert_execucao_analitica() from public, anon, authenticated;
revoke execute on function public.agp_calcular_completude_instrumento(uuid,jsonb) from public, anon;
revoke execute on function public.agp_can_manage_institution(uuid) from public, anon;
revoke execute on function public.agp_consentimento_vigente(uuid,uuid,text) from public, anon;
revoke execute on function public.agp_elegibilidade_operacional(uuid) from public, anon;
revoke execute on function public.agp_has_institution_access(uuid) from public, anon;
revoke execute on function public.agp_instrumentos_ativos_disponiveis(uuid,text,text) from public, anon;
revoke execute on function public.agp_is_owner() from public, anon;
revoke execute on function public.agp_linha_base_vigente(uuid,uuid) from public, anon;
revoke execute on function public.agp_pode_analisar(uuid,uuid) from public, anon;
revoke execute on function public.agp_pode_coletar(uuid,uuid) from public, anon;
revoke execute on function public.agp_preparar_coleta() from public, anon, authenticated;
revoke execute on function public.agp_profissional_pode_projeto(uuid) from public, anon;
revoke execute on function public.agp_project_institution(uuid) from public, anon;
revoke execute on function public.agp_project_institution_id(uuid) from public, anon;
revoke execute on function public.agp_registrar_resultado_analitico() from public, anon, authenticated;
revoke execute on function public.agp_registrar_versao_coleta() from public, anon, authenticated;
revoke execute on function public.agp_status_onboarding_participante(uuid) from public, anon;
revoke execute on function public.agp_sync_participante_atleta_projeto() from public, anon, authenticated;
revoke execute on function public.agp_user_can_access_institution(uuid) from public, anon;
revoke execute on function public.handle_new_user() from public, anon, authenticated;
