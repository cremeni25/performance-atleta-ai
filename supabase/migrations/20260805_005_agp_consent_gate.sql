begin;

-- AGP-34 — Consentimento operacional obrigatório
-- Aplicar exclusivamente no projeto AGP: kvmtfngxkeodkqrxbjwo

alter table public.agp_consentimentos
  add column if not exists projeto_id uuid references public.agp_projetos_validacao(id) on delete cascade,
  add column if not exists participante_id uuid references public.agp_participantes_projeto(id) on delete cascade,
  add column if not exists concedido_por_auth_id uuid references auth.users(id),
  add column if not exists tipo_consentimento text not null default 'tratamento_dados_esportivos',
  add column if not exists hash_termo text,
  add column if not exists ip_origem text,
  add column if not exists user_agent text;

create unique index if not exists agp_consentimento_vigente_uidx
on public.agp_consentimentos (atleta_id, projeto_id, finalidade)
where revogado_em is null;

create or replace function public.agp_consentimento_vigente(
  p_atleta_id uuid,
  p_projeto_id uuid,
  p_finalidade text default 'monitoramento_esportivo'
)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.agp_consentimentos c
    where c.atleta_id = p_atleta_id
      and c.projeto_id = p_projeto_id
      and c.finalidade = p_finalidade
      and c.revogado_em is null
      and c.concedido_em <= now()
  );
$$;

create or replace function public.agp_pode_coletar(
  p_atleta_id uuid,
  p_projeto_id uuid
)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select public.agp_consentimento_vigente(
    p_atleta_id,
    p_projeto_id,
    'monitoramento_esportivo'
  );
$$;

create or replace function public.agp_assert_consentimento_coleta()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if not public.agp_pode_coletar(new.atleta_id, new.projeto_id) then
    raise exception 'CONSENTIMENTO_OBRIGATORIO: coleta bloqueada para atleta/projeto sem consentimento vigente';
  end if;
  return new;
end;
$$;

drop trigger if exists agp_coletas_consentimento_gate on public.agp_coletas;
create trigger agp_coletas_consentimento_gate
before insert or update of atleta_id, projeto_id, dados, status
on public.agp_coletas
for each row
execute function public.agp_assert_consentimento_coleta();

create or replace view public.agp_status_consentimentos as
select
  pp.id as participante_id,
  pp.projeto_id,
  pp.pessoa_id,
  pe.legacy_perfil_atleta_id as atleta_id,
  p.nome,
  public.agp_consentimento_vigente(
    pe.legacy_perfil_atleta_id,
    pp.projeto_id,
    'monitoramento_esportivo'
  ) as consentimento_vigente,
  (
    select max(c.concedido_em)
    from public.agp_consentimentos c
    where c.atleta_id = pe.legacy_perfil_atleta_id
      and c.projeto_id = pp.projeto_id
      and c.finalidade = 'monitoramento_esportivo'
      and c.revogado_em is null
  ) as concedido_em
from public.agp_participantes_projeto pp
join public.agp_pessoas p on p.id = pp.pessoa_id
left join public.agp_perfis_esportivos pe on pe.pessoa_id = pp.pessoa_id
where pp.funcao_no_projeto = 'atleta'
  and pp.ativo = true;

grant select on public.agp_status_consentimentos to authenticated;
grant execute on function public.agp_consentimento_vigente(uuid, uuid, text) to authenticated;
grant execute on function public.agp_pode_coletar(uuid, uuid) to authenticated;

commit;
