update public.agp_perfis_especializacao_esportiva
set metadados = coalesce(metadados,'{}'::jsonb) || jsonb_build_object(
  'scientific_source_count',48,
  'bibliographic_review_verified',48,
  'methodological_review_verified',48,
  'professional_validation_pending',48,
  'scientific_status','awaiting_professional_validation',
  'scientific_review_required_before_approval',true,
  'do_not_use_for_scientific_inference',true,
  'last_structural_update','2026-09-16'
), updated_at=now()
where codigo='AGP-SWIMMING-POOL' and versao='1.0.0';
