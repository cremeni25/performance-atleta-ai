begin;

-- Corrige a semântica do onboarding: ausência de instrumento compatível
-- é bloqueio operacional de elegibilidade, não pendência de perfil esportivo.

create or replace function public.agp_status_onboarding_participante(p_participante_id uuid)
returns text
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  v_funcao text;
  v_resultado jsonb;
begin
  select funcao_no_projeto into v_funcao
  from public.agp_participantes_projeto
  where id = p_participante_id;

  if not found then return 'rascunho'; end if;
  if v_funcao <> 'atleta' then return 'apto_para_coleta'; end if;

  v_resultado := public.agp_elegibilidade_operacional(p_participante_id);

  if (v_resultado -> 'pendencias') ? 'perfil_esportivo_pendente' then return 'perfil_pendente'; end if;
  if (v_resultado -> 'pendencias') ? 'tecnico_responsavel_pendente' then return 'vinculo_pendente'; end if;
  if (v_resultado -> 'pendencias') ? 'tecnico_responsavel_invalido' then return 'vinculo_pendente'; end if;
  if (v_resultado -> 'pendencias') ? 'consentimento_pendente' then return 'consentimento_pendente'; end if;
  if (v_resultado -> 'pendencias') ? 'linha_base_pendente' then return 'linha_base_pendente'; end if;
  if coalesce((v_resultado ->> 'apto_coleta')::boolean, false) then return 'apto_para_coleta'; end if;

  -- Se chegou até aqui, o onboarding estrutural está concluído.
  -- Ex.: instrumento_indisponivel continua bloqueando coleta/análise na elegibilidade,
  -- mas não deve transformar o atleta em perfil_pendente.
  return 'ativo';
end;
$$;

update public.agp_participantes_projeto pp
set status_onboarding = public.agp_status_onboarding_participante(pp.id),
    updated_at = now()
where pp.ativo = true;

grant execute on function public.agp_status_onboarding_participante(uuid) to authenticated;

commit;
