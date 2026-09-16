-- AGP longitudinal hierarchy integrity + neutral operational coverage.
-- No score or recommendation is produced here.

create or replace function public.agp_validar_hierarquia_ciclo_longitudinal()
returns trigger
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
declare
  parent_row public.agp_ciclos_longitudinais%rowtype;
  expected_parent text;
begin
  if new.nivel = 'carreira' then
    if new.ciclo_pai_id is not null then
      raise exception 'Ciclo carreira não pode possuir ciclo pai';
    end if;
    return new;
  end if;

  expected_parent := case new.nivel
    when 'temporada' then 'carreira'
    when 'mesociclo' then 'temporada'
    when 'microciclo' then 'mesociclo'
    when 'dia' then 'microciclo'
    else null
  end;

  if new.ciclo_pai_id is null then
    raise exception 'Ciclo % exige ciclo pai do nível %', new.nivel, expected_parent;
  end if;

  select * into parent_row
  from public.agp_ciclos_longitudinais
  where id = new.ciclo_pai_id;

  if not found then
    raise exception 'Ciclo pai inexistente';
  end if;

  if parent_row.pessoa_id <> new.pessoa_id then
    raise exception 'Ciclo pai e filho devem pertencer à mesma pessoa';
  end if;

  if parent_row.nivel <> expected_parent then
    raise exception 'Ciclo % exige pai %, recebido %', new.nivel, expected_parent, parent_row.nivel;
  end if;

  if new.inicio < parent_row.inicio then
    raise exception 'Início do ciclo filho não pode anteceder o ciclo pai';
  end if;

  if parent_row.fim is not null and new.inicio > parent_row.fim then
    raise exception 'Início do ciclo filho está fora da janela do ciclo pai';
  end if;

  if parent_row.fim is not null and new.fim is not null and new.fim > parent_row.fim then
    raise exception 'Fim do ciclo filho está fora da janela do ciclo pai';
  end if;

  return new;
end;
$$;

drop trigger if exists trg_agp_validar_hierarquia_ciclo_longitudinal on public.agp_ciclos_longitudinais;
create trigger trg_agp_validar_hierarquia_ciclo_longitudinal
before insert or update of pessoa_id,ciclo_pai_id,nivel,inicio,fim
on public.agp_ciclos_longitudinais
for each row execute function public.agp_validar_hierarquia_ciclo_longitudinal();

create or replace view public.agp_cobertura_ciclos_longitudinais
with (security_invoker = true)
as
select
  c.id as ciclo_id,
  c.pessoa_id,
  c.participante_id,
  c.projeto_id,
  c.perfil_especializacao_id,
  c.nivel,
  c.codigo,
  c.nome,
  c.inicio,
  c.fim,
  c.status,
  (select count(*) from public.agp_ciclo_sessoes x where x.ciclo_id = c.id) as sessoes_vinculadas,
  (select count(*) from public.agp_ciclo_participacoes_prova x where x.ciclo_id = c.id) as provas_vinculadas,
  (select count(*) from public.agp_ciclo_coletas x where x.ciclo_id = c.id) as coletas_vinculadas,
  (select count(*) from public.agp_ciclo_intervencoes x where x.ciclo_id = c.id) as intervencoes_vinculadas,
  (select count(*) from public.agp_ciclo_respostas_intervencao x where x.ciclo_id = c.id) as respostas_intervencao_vinculadas,
  jsonb_build_object(
    'sessoes', (select count(*) from public.agp_ciclo_sessoes x where x.ciclo_id = c.id),
    'provas', (select count(*) from public.agp_ciclo_participacoes_prova x where x.ciclo_id = c.id),
    'coletas', (select count(*) from public.agp_ciclo_coletas x where x.ciclo_id = c.id),
    'intervencoes', (select count(*) from public.agp_ciclo_intervencoes x where x.ciclo_id = c.id),
    'respostas_intervencao', (select count(*) from public.agp_ciclo_respostas_intervencao x where x.ciclo_id = c.id)
  ) as cobertura_operacional
from public.agp_ciclos_longitudinais c;

revoke all on public.agp_cobertura_ciclos_longitudinais from public, anon, authenticated;
grant select on public.agp_cobertura_ciclos_longitudinais to service_role;
