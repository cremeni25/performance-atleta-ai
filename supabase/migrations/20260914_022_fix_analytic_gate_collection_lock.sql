begin;

create or replace function public.agp_assert_execucao_analitica()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_elegibilidade jsonb;
  v_total integer;
  v_invalidas integer;
begin
  v_elegibilidade := public.agp_elegibilidade_operacional(new.participante_id);
  if not coalesce((v_elegibilidade ->> 'apto_analise')::boolean, false) then
    raise exception 'ELEGIBILIDADE_ANALISE_NEGADA: %', v_elegibilidade -> 'pendencias';
  end if;

  if new.status in ('executando','concluida') then
    select count(*), count(*) filter (
      where c.status <> 'validada'
         or c.bloqueado_para_edicao is not true
         or c.liberado_motor_em is null
         or rv.id is null
    ) into v_total, v_invalidas
    from public.agp_execucao_entradas ei
    join public.agp_coletas c on c.id = ei.coleta_id
    left join public.agp_respostas_coleta_versoes rv on rv.id = ei.versao_resposta_id
    where ei.execucao_id = new.id;

    if v_total = 0 then
      raise exception 'ENTRADAS_ANALITICAS_OBRIGATORIAS';
    end if;
    if v_invalidas > 0 then
      raise exception 'ENTRADA_ANALITICA_INVALIDA: somente coletas validadas, bloqueadas e liberadas ao motor';
    end if;
  end if;

  new.updated_at := now();
  return new;
end;
$$;

commit;
