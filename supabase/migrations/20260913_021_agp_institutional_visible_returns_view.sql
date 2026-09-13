begin;

create or replace view public.agp_retornos_institucionais_visiveis
with (security_invoker=true)
as
select id, participante_id, projeto_id, data_avaliacao, classificacao_resposta, conclusao, recomendacao_proximo_ciclo
from public.agp_respostas_intervencao
where visivel_instituicao is true;

grant select on public.agp_retornos_institucionais_visiveis to authenticated;

commit;
