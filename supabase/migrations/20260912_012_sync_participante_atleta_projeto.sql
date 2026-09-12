begin;

create or replace function public.agp_sync_participante_atleta_projeto()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_atleta_id uuid;
  v_tecnico_auth_id uuid;
begin
  if new.funcao_no_projeto <> 'atleta' or new.projeto_id is null then
    return new;
  end if;

  select pe.legacy_perfil_atleta_id
    into v_atleta_id
  from public.agp_perfis_esportivos pe
  where pe.pessoa_id = new.pessoa_id
    and pe.status = 'ativo'
    and pe.legacy_perfil_atleta_id is not null
  order by pe.updated_at desc nulls last, pe.created_at desc
  limit 1;

  if v_atleta_id is null then
    return new;
  end if;

  if new.tecnico_responsavel_pessoa_id is not null then
    select ca.auth_id
      into v_tecnico_auth_id
    from public.agp_contas_acesso ca
    where ca.pessoa_id = new.tecnico_responsavel_pessoa_id
      and ca.auth_id is not null
    limit 1;
  end if;

  insert into public.agp_atletas_projeto (
    projeto_id, atleta_id, tecnico_responsavel_auth_id,
    status, data_entrada, data_saida
  ) values (
    new.projeto_id,
    v_atleta_id,
    v_tecnico_auth_id,
    case when new.ativo then 'ativo' else 'retirado' end,
    coalesce(new.data_inicio, current_date),
    case when new.ativo then null else coalesce(new.data_fim, current_date) end
  )
  on conflict (projeto_id, atleta_id)
  do update set
    tecnico_responsavel_auth_id = excluded.tecnico_responsavel_auth_id,
    status = excluded.status,
    data_saida = excluded.data_saida;

  return new;
end;
$$;

drop trigger if exists agp_participantes_sync_atleta_projeto on public.agp_participantes_projeto;
create trigger agp_participantes_sync_atleta_projeto
after insert or update of projeto_id, pessoa_id, tecnico_responsavel_pessoa_id, ativo, data_inicio, data_fim
on public.agp_participantes_projeto
for each row execute function public.agp_sync_participante_atleta_projeto();

insert into public.agp_atletas_projeto (
  projeto_id, atleta_id, tecnico_responsavel_auth_id,
  status, data_entrada, data_saida
)
select
  pp.projeto_id,
  pe.legacy_perfil_atleta_id,
  ca.auth_id,
  case when pp.ativo then 'ativo' else 'retirado' end,
  coalesce(pp.data_inicio, current_date),
  case when pp.ativo then null else coalesce(pp.data_fim, current_date) end
from public.agp_participantes_projeto pp
join public.agp_perfis_esportivos pe
  on pe.pessoa_id = pp.pessoa_id
 and pe.status = 'ativo'
 and pe.legacy_perfil_atleta_id is not null
left join public.agp_contas_acesso ca
  on ca.pessoa_id = pp.tecnico_responsavel_pessoa_id
where pp.funcao_no_projeto = 'atleta'
  and pp.projeto_id is not null
on conflict (projeto_id, atleta_id)
do update set
  tecnico_responsavel_auth_id = excluded.tecnico_responsavel_auth_id,
  status = excluded.status,
  data_saida = excluded.data_saida;

commit;
