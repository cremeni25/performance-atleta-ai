begin;

-- AGP-38 — Instâncias de aplicação, respostas versionadas e completude
-- Aplicar exclusivamente no projeto AGP: kvmtfngxkeodkqrxbjwo

alter table public.agp_coletas
  add column if not exists participante_id uuid references public.agp_participantes_projeto(id) on delete set null,
  add column if not exists ativacao_instrumento_id uuid references public.agp_ativacoes_instrumentos(id) on delete restrict,
  add column if not exists versao_instrumento text,
  add column if not exists versao_schema text not null default '1.0.0',
  add column if not exists ciclo_referencia text,
  add column if not exists janela_inicio timestamptz,
  add column if not exists janela_fim timestamptz,
  add column if not exists iniciado_em timestamptz,
  add column if not exists submetido_em timestamptz,
  add column if not exists bloqueado_para_edicao boolean not null default false,
  add column if not exists liberado_motor_em timestamptz,
  add column if not exists hash_resposta text,
  add column if not exists updated_at timestamptz not null default now();

create table if not exists public.agp_respostas_coleta_versoes (
  id uuid primary key default gen_random_uuid(),
  coleta_id uuid not null references public.agp_coletas(id) on delete cascade,
  numero_versao integer not null,
  dados jsonb not null,
  completude numeric(5,2) not null check (completude between 0 and 100),
  status text not null check (status in ('rascunho','completa','validada','rejeitada','corrigida')),
  motivo_alteracao text,
  criado_por_auth_id uuid references auth.users(id) on delete set null,
  hash_resposta text not null,
  created_at timestamptz not null default now(),
  unique (coleta_id, numero_versao)
);

create index if not exists agp_coletas_participante_idx on public.agp_coletas(participante_id, data_hora_coleta desc);
create index if not exists agp_respostas_coleta_versoes_idx on public.agp_respostas_coleta_versoes(coleta_id, numero_versao desc);

create or replace function public.agp_calcular_completude_instrumento(p_instrumento_id uuid, p_dados jsonb)
returns numeric
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  v_schema jsonb;
  v_regra jsonb;
  v_obrigatorios jsonb := '[]'::jsonb;
  v_total integer := 0;
  v_preenchidos integer := 0;
  v_campo text;
begin
  select schema_campos, regra_completude into v_schema, v_regra
  from public.agp_instrumentos where id = p_instrumento_id;
  if not found then return 0; end if;
  v_obrigatorios := coalesce(v_regra -> 'campos_obrigatorios', v_schema -> 'required', '[]'::jsonb);
  v_total := jsonb_array_length(v_obrigatorios);
  if v_total = 0 then return case when p_dados = '{}'::jsonb then 0 else 100 end; end if;
  for v_campo in select jsonb_array_elements_text(v_obrigatorios)
  loop
    if p_dados ? v_campo and p_dados -> v_campo is not null and p_dados -> v_campo <> 'null'::jsonb and p_dados ->> v_campo <> '' then
      v_preenchidos := v_preenchidos + 1;
    end if;
  end loop;
  return round((v_preenchidos::numeric / v_total::numeric) * 100, 2);
end;
$$;

create or replace function public.agp_preparar_coleta()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_eligibilidade jsonb;
  v_instrumento_ativo boolean := false;
begin
  if new.participante_id is not null then
    v_eligibilidade := public.agp_elegibilidade_operacional(new.participante_id);
    if not coalesce((v_eligibilidade ->> 'apto_coleta')::boolean, false) then
      raise exception 'ELEGIBILIDADE_COLETA_NEGADA:%', coalesce(v_eligibilidade -> 'pendencias', '[]'::jsonb)::text;
    end if;
  end if;
  if new.ativacao_instrumento_id is not null then
    select exists(
      select 1 from public.agp_ativacoes_instrumentos ai
      join public.agp_instrumentos i on i.id = ai.instrumento_id
      join public.agp_protocolos p on p.id = i.protocolo_id
      where ai.id = new.ativacao_instrumento_id and ai.instrumento_id = new.instrumento_id
        and ai.ativo = true and ai.aprovado_em is not null
        and current_date between ai.data_inicio and coalesce(ai.data_fim, 'infinity'::date)
        and i.ativo = true and i.status_catalogo = 'aprovado'
        and p.ativo = true and p.status_catalogo = 'aprovado'
    ) into v_instrumento_ativo;
    if not v_instrumento_ativo then raise exception 'INSTRUMENTO_NAO_ATIVADO'; end if;
  end if;
  if new.bloqueado_para_edicao and tg_op = 'UPDATE' and new.dados is distinct from old.dados then
    raise exception 'COLETA_BLOQUEADA_PARA_EDICAO';
  end if;
  new.completude := public.agp_calcular_completude_instrumento(new.instrumento_id, new.dados);
  new.versao_instrumento := coalesce(new.versao_instrumento, (select versao from public.agp_instrumentos where id = new.instrumento_id));
  new.hash_resposta := encode(digest(coalesce(new.dados::text, '{}') || ':' || coalesce(new.versao_schema, '1.0.0'), 'sha256'), 'hex');
  new.updated_at := now();
  if new.status in ('completa','validada') and new.completude < 100 then raise exception 'COLETA_INCOMPLETA:%', new.completude; end if;
  if new.status = 'validada' then
    new.submetido_em := coalesce(new.submetido_em, now());
    new.bloqueado_para_edicao := true;
    new.liberado_motor_em := coalesce(new.liberado_motor_em, now());
  end if;
  return new;
end;
$$;

drop trigger if exists agp_coletas_preparacao on public.agp_coletas;
create trigger agp_coletas_preparacao before insert or update on public.agp_coletas
for each row execute function public.agp_preparar_coleta();

create or replace function public.agp_registrar_versao_coleta()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare v_numero integer;
begin
  if tg_op = 'INSERT' or new.dados is distinct from old.dados or new.status is distinct from old.status then
    select coalesce(max(numero_versao), 0) + 1 into v_numero from public.agp_respostas_coleta_versoes where coleta_id = new.id;
    insert into public.agp_respostas_coleta_versoes (coleta_id, numero_versao, dados, completude, status, motivo_alteracao, criado_por_auth_id, hash_resposta)
    values (new.id, v_numero, new.dados, new.completude, new.status, new.justificativa_correcao, auth.uid(), encode(digest(coalesce(new.dados::text, '{}') || ':' || new.status || ':' || v_numero::text, 'sha256'), 'hex'));
  end if;
  return new;
end;
$$;

drop trigger if exists agp_coletas_versionamento on public.agp_coletas;
create trigger agp_coletas_versionamento after insert or update of dados, status on public.agp_coletas
for each row execute function public.agp_registrar_versao_coleta();

create or replace view public.agp_coletas_operacionais as
select c.id as coleta_id, c.participante_id, c.atleta_id, c.projeto_id, c.instrumento_id, c.ativacao_instrumento_id,
  i.codigo as instrumento_codigo, i.nome as instrumento_nome, c.versao_instrumento, c.versao_schema,
  c.ciclo_referencia, c.janela_inicio, c.janela_fim, c.status, c.completude, c.bloqueado_para_edicao,
  c.liberado_motor_em, c.data_hora_coleta, c.updated_at, coalesce(v.numero_versao, 0) as ultima_versao
from public.agp_coletas c
join public.agp_instrumentos i on i.id = c.instrumento_id
left join lateral (
  select numero_versao from public.agp_respostas_coleta_versoes rv
  where rv.coleta_id = c.id order by numero_versao desc limit 1
) v on true;

alter table public.agp_respostas_coleta_versoes enable row level security;
create policy agp_respostas_versoes_owner_read on public.agp_respostas_coleta_versoes for select using (public.agp_is_owner());
create policy agp_respostas_versoes_institution_read on public.agp_respostas_coleta_versoes for select using (
  exists (select 1 from public.agp_coletas c where c.id = coleta_id and public.agp_user_can_access_institution(public.agp_project_institution_id(c.projeto_id)))
);

grant execute on function public.agp_calcular_completude_instrumento(uuid,jsonb) to authenticated;
grant select on public.agp_coletas_operacionais to authenticated;
grant select on public.agp_respostas_coleta_versoes to authenticated;

commit;
