begin;

-- AGP-36 — Elegibilidade operacional unificada
-- Aplicar exclusivamente no projeto AGP: kvmtfngxkeodkqrxbjwo

create or replace function public.agp_instrumentos_ativos_disponiveis(
  p_projeto_id uuid,
  p_modalidade text default null,
  p_categoria text default null
)
returns integer
language sql
stable
security definer
set search_path = public
as $$
  select count(*)::integer
  from public.agp_instrumentos i
  join public.agp_protocolos p on p.id = i.protocolo_id
  where i.ativo = true
    and p.ativo = true
    and (p.instituicao_id is null or p.instituicao_id = public.agp_project_institution(p_projeto_id))
    and (p.modalidade is null or p_modalidade is null or lower(p.modalidade) = lower(p_modalidade))
    and (p.categoria is null or p_categoria is null or lower(p.categoria) = lower(p_categoria));
$$;

create or replace function public.agp_elegibilidade_operacional(p_participante_id uuid)
returns jsonb
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  v_participante public.agp_participantes_projeto%rowtype;
  v_modalidade text;
  v_categoria text;
  v_atleta_id uuid;
  v_tecnico_ativo boolean := false;
  v_consentimento boolean := false;
  v_linha_base boolean := false;
  v_instrumentos integer := 0;
  v_pendencias jsonb := '[]'::jsonb;
  v_coleta boolean := false;
  v_analise boolean := false;
begin
  select * into v_participante
  from public.agp_participantes_projeto
  where id = p_participante_id;

  if not found then
    return jsonb_build_object(
      'participante_id', p_participante_id,
      'apto_coleta', false,
      'apto_analise', false,
      'pendencias', jsonb_build_array('participante_inexistente')
    );
  end if;

  select pe.legacy_perfil_atleta_id, pe.modalidade, pe.categoria
    into v_atleta_id, v_modalidade, v_categoria
  from public.agp_perfis_esportivos pe
  where pe.pessoa_id = v_participante.pessoa_id
    and pe.status = 'ativo';

  if not v_participante.ativo then
    v_pendencias := v_pendencias || jsonb_build_array('participante_inativo');
  end if;

  if v_participante.funcao_no_projeto = 'atleta' then
    if v_atleta_id is null then
      v_pendencias := v_pendencias || jsonb_build_array('perfil_esportivo_pendente');
    end if;

    if v_participante.tecnico_responsavel_pessoa_id is null then
      v_pendencias := v_pendencias || jsonb_build_array('tecnico_responsavel_pendente');
    else
      select exists(
        select 1
        from public.agp_participantes_projeto tp
        where tp.projeto_id = v_participante.projeto_id
          and tp.pessoa_id = v_participante.tecnico_responsavel_pessoa_id
          and tp.funcao_no_projeto in ('tecnico','treinador','preparador_fisico')
          and tp.ativo = true
      ) into v_tecnico_ativo;
      if not v_tecnico_ativo then
        v_pendencias := v_pendencias || jsonb_build_array('tecnico_responsavel_invalido');
      end if;
    end if;

    if v_atleta_id is not null then
      v_consentimento := public.agp_consentimento_vigente(v_atleta_id, v_participante.projeto_id, 'monitoramento_esportivo');
      v_linha_base := public.agp_linha_base_vigente(v_atleta_id, v_participante.projeto_id);
    end if;

    if not v_consentimento then
      v_pendencias := v_pendencias || jsonb_build_array('consentimento_pendente');
    end if;
    if not v_linha_base then
      v_pendencias := v_pendencias || jsonb_build_array('linha_base_pendente');
    end if;

    v_instrumentos := public.agp_instrumentos_ativos_disponiveis(v_participante.projeto_id, v_modalidade, v_categoria);
    if v_instrumentos = 0 then
      v_pendencias := v_pendencias || jsonb_build_array('instrumento_indisponivel');
    end if;

    v_coleta := v_participante.ativo
      and v_atleta_id is not null
      and v_tecnico_ativo
      and v_consentimento
      and v_instrumentos > 0;

    v_analise := v_coleta and v_linha_base;
  else
    v_coleta := v_participante.ativo;
    v_analise := v_participante.ativo;
  end if;

  return jsonb_build_object(
    'participante_id', v_participante.id,
    'projeto_id', v_participante.projeto_id,
    'pessoa_id', v_participante.pessoa_id,
    'atleta_id', v_atleta_id,
    'tecnico_responsavel_valido', v_tecnico_ativo,
    'consentimento_vigente', v_consentimento,
    'linha_base_vigente', v_linha_base,
    'instrumentos_ativos', v_instrumentos,
    'apto_coleta', v_coleta,
    'apto_analise', v_analise,
    'pendencias', v_pendencias
  );
end;
$$;

create or replace view public.agp_elegibilidade_operacional_projeto as
select
  pp.id as participante_id,
  pp.projeto_id,
  pp.pessoa_id,
  p.nome,
  pp.funcao_no_projeto,
  pp.tecnico_responsavel_pessoa_id,
  e.resultado ->> 'atleta_id' as atleta_id,
  coalesce((e.resultado ->> 'tecnico_responsavel_valido')::boolean, false) as tecnico_responsavel_valido,
  coalesce((e.resultado ->> 'consentimento_vigente')::boolean, false) as consentimento_vigente,
  coalesce((e.resultado ->> 'linha_base_vigente')::boolean, false) as linha_base_vigente,
  coalesce((e.resultado ->> 'instrumentos_ativos')::integer, 0) as instrumentos_ativos,
  coalesce((e.resultado ->> 'apto_coleta')::boolean, false) as apto_coleta,
  coalesce((e.resultado ->> 'apto_analise')::boolean, false) as apto_analise,
  e.resultado -> 'pendencias' as pendencias,
  pp.ativo
from public.agp_participantes_projeto pp
join public.agp_pessoas p on p.id = pp.pessoa_id
cross join lateral (
  select public.agp_elegibilidade_operacional(pp.id) as resultado
) e;

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
  if (v_resultado -> 'pendencias') ? 'instrumento_indisponivel' then return 'perfil_pendente'; end if;
  if coalesce((v_resultado ->> 'apto_coleta')::boolean, false) then return 'apto_para_coleta'; end if;

  return 'rascunho';
end;
$$;

grant execute on function public.agp_instrumentos_ativos_disponiveis(uuid,text,text) to authenticated;
grant execute on function public.agp_elegibilidade_operacional(uuid) to authenticated;
grant select on public.agp_elegibilidade_operacional_projeto to authenticated;

commit;
