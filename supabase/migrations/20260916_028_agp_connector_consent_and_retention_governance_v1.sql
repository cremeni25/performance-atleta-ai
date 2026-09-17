-- AGP connector governance v1
-- External evidence ingestion must be explicitly authorized, revocable and retention-aware.
-- Participant-level connectors require a current AGP consent record before activation or ingestion.

alter table public.agp_ativacoes_conectores
  add column if not exists consentimento_id uuid null references public.agp_consentimentos(id) on delete restrict,
  add column if not exists finalidade_ingestao text not null default 'monitoramento_esportivo_autorizado',
  add column if not exists politica_retencao jsonb not null default '{"modo":"conforme_politica_institucional_e_legal"}'::jsonb,
  add column if not exists revogado_em timestamptz null,
  add column if not exists ultima_revalidacao_em timestamptz null;

alter table public.agp_ingestoes_externas
  add column if not exists expira_em timestamptz null,
  add column if not exists minimizado_em timestamptz null,
  add column if not exists payload_minimizado boolean not null default false;

create or replace function public.agp_validar_ativacao_conector()
returns trigger
language plpgsql
set search_path = public
as $$
declare
  c public.agp_consentimentos%rowtype;
begin
  if new.participante_id is not null then
    if new.consentimento_id is null then
      raise exception 'Participant-level connector activation requires consentimento_id';
    end if;

    select * into c
    from public.agp_consentimentos
    where id=new.consentimento_id;

    if not found then
      raise exception 'Connector consent record not found';
    end if;
    if c.participante_id is distinct from new.participante_id then
      raise exception 'Connector consent does not belong to activation participant';
    end if;
    if new.projeto_id is not null and c.projeto_id is distinct from new.projeto_id then
      raise exception 'Connector consent project does not match activation project';
    end if;
    if c.concedido_em is null or c.revogado_em is not null then
      raise exception 'Connector consent is not currently valid';
    end if;
  end if;

  if new.revogado_em is not null and new.status='ativo' then
    raise exception 'Revoked connector activation cannot remain active';
  end if;

  return new;
end;
$$;

drop trigger if exists trg_agp_validar_ativacao_conector on public.agp_ativacoes_conectores;
create trigger trg_agp_validar_ativacao_conector
before insert or update on public.agp_ativacoes_conectores
for each row execute function public.agp_validar_ativacao_conector();

create or replace function public.agp_validar_ingestao_conector()
returns trigger
language plpgsql
set search_path = public
as $$
declare
  a public.agp_ativacoes_conectores%rowtype;
begin
  select * into a
  from public.agp_ativacoes_conectores
  where id=new.ativacao_id;

  if not found then
    raise exception 'Connector activation not found';
  end if;
  if a.conector_id is distinct from new.conector_id then
    raise exception 'Ingestion connector differs from activation connector';
  end if;
  if a.status <> 'ativo' or a.revogado_em is not null then
    raise exception 'Connector activation is not active';
  end if;
  if a.inicio is not null and coalesce(new.ocorrido_em,new.recebido_em,now()) < a.inicio then
    raise exception 'Ingestion precedes connector authorization window';
  end if;
  if a.fim is not null and coalesce(new.ocorrido_em,new.recebido_em,now()) > a.fim then
    raise exception 'Ingestion exceeds connector authorization window';
  end if;
  if a.participante_id is not null and new.participante_id is distinct from a.participante_id then
    raise exception 'Ingestion participant differs from authorized activation participant';
  end if;
  if a.projeto_id is not null and new.projeto_id is distinct from a.projeto_id then
    raise exception 'Ingestion project differs from authorized activation project';
  end if;

  return new;
end;
$$;

drop trigger if exists trg_agp_validar_ingestao_conector on public.agp_ingestoes_externas;
create trigger trg_agp_validar_ingestao_conector
before insert or update on public.agp_ingestoes_externas
for each row execute function public.agp_validar_ingestao_conector();

create or replace view public.agp_governanca_conectores_status
with (security_invoker = true)
as
select
  a.id as ativacao_id,
  a.conector_id,
  c.codigo as conector_codigo,
  c.nome as conector_nome,
  a.instituicao_id,
  a.projeto_id,
  a.participante_id,
  a.status,
  a.inicio,
  a.fim,
  a.revogado_em,
  a.consentimento_id,
  case
    when a.participante_id is not null and a.consentimento_id is null then 'consentimento_ausente'
    when a.revogado_em is not null then 'revogado'
    when a.status <> 'ativo' then 'nao_ativo'
    when a.fim is not null and a.fim < now() then 'expirado'
    else 'autorizacao_operacional_vigente'
  end as estado_governanca,
  a.politica_retencao,
  a.ultima_revalidacao_em
from public.agp_ativacoes_conectores a
join public.agp_conectores_evidencia c on c.id=a.conector_id;

revoke all on public.agp_governanca_conectores_status from public,anon,authenticated;
grant select on public.agp_governanca_conectores_status to service_role;

comment on column public.agp_ativacoes_conectores.consentimento_id is
'Participant-level connector authorization must reference an unrevoked AGP consent record before activation.';
comment on column public.agp_ingestoes_externas.payload_minimizado is
'Indicates whether the original external payload has undergone governed minimization according to retention policy.';
comment on view public.agp_governanca_conectores_status is
'Operational governance gate for external evidence connectors: authorization, revocation and retention context without treating vendor data as canonical truth.';
