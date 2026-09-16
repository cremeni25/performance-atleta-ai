-- Pin search_path for remaining functions reported by Supabase security advisor.

alter function public.agp_calcular_completude_linha_base(public.agp_linhas_base_atleta)
  set search_path = public, pg_temp;

alter function public.iniciar_estado_comercial()
  set search_path = public, pg_temp;
