begin;

-- AGP-35 — Linha de base operacional e bloqueio de análises.
-- Aplicar exclusivamente no projeto AGP: kvmtfngxkeodkqrxbjwo

alter table public.agp_linhas_base_atleta
  add column if not exists participante_id uuid references public.agp_participantes_projeto(id) on delete cascade,
  add column if not exists status text not null default 'rascunho' check (status in ('rascunho','completa','validada','substituida')),
  add column if not exists completude numeric(5,2) not null default 0 check (completude between 0 and 100),
  add column if not exists validado_por_auth_id uuid references auth.users(id),
  add column if not exists validado_em timestamptz,
  add column if not exists updated_at timestamptz not null default now();

create unique index if not exists agp_linha_base_ativa_uidx
on public.agp_linhas_base_atleta (atleta_id, projeto_id)
where status in ('completa','validada');

create or replace function public.agp_calcular_completude_linha_base(p_linha public.agp_linhas_base_atleta)
returns numeric
language sql
immutable
as $$
  select round((
    (case when p_linha.idade_cronologica is not null then 1 else 0 end) +
    (case when nullif(trim(p_linha.modalidade), '') is not null then 1 else 0 end) +
    (case when nullif(trim(p_linha.categoria), '') is not null then 1 else 0 end) +
    (case when nullif(trim(p_linha.sexo_registrado), '') is not null then 1 else 0 end) +
    (case when p_linha.altura_cm is not null then 1 else 0 end) +
    (case when p_linha.massa_kg is not null then 1 else 0 end) +
    (case when p_linha.data_referencia is not null then 1 else 0 end) +
    (case when nullif(trim(p_linha.origem), '') is not null then 1 else 0 end)
  ) * 100.0 / 8, 2);
$$;

create or replace function public.agp_normalizar_linha_base()
returns trigger
language plpgsql
as $$
begin
  new.completude := public.agp_calcular_completude_linha_base(new);
  new.updated_at := now();
  if new.completude = 100 and new.status = 'rascunho' then
    new.status := 'completa';
  elsif new.completude < 100 and new.status in ('completa','validada') then
    raise exception 'LINHA_BASE_INCOMPLETA: idade, modalidade, categoria, sexo, altura, massa, data e origem são obrigatórios';
  end if;
  return new;
end;
$$;

drop trigger if exists agp_linhas_base_normalizar on public.agp_linhas_base_atleta;
create trigger agp_linhas_base_normalizar
before insert or update on public.agp_linhas_base_atleta
for each row execute function public.agp_normalizar_linha_base();

create or replace function public.agp_linha_base_vigente(p_atleta_id uuid, p_projeto_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.agp_linhas_base_atleta lb
    where lb.atleta_id = p_atleta_id
      and lb.projeto_id = p_projeto_id
      and lb.status in ('completa','validada')
      and lb.completude = 100
  );
$$;

create or replace function public.agp_pode_analisar(p_atleta_id uuid, p_projeto_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select public.agp_consentimento_vigente(p_atleta_id, p_projeto_id, 'monitoramento_esportivo')
     and public.agp_linha_base_vigente(p_atleta_id, p_projeto_id);
$$;

create or replace function public.agp_assert_linha_base_analise()
returns trigger
language plpgsql
as $$
begin
  if new.projeto_id is null or not public.agp_pode_analisar(new.atleta_id, new.projeto_id) then
    raise exception 'LINHA_BASE_OBRIGATORIA: análise bloqueada sem consentimento e linha de base completa';
  end if;
  return new;
end;
$$;

drop trigger if exists agp_resultados_linha_base_gate on public.agp_resultados_analiticos;
create trigger agp_resultados_linha_base_gate
before insert or update on public.agp_resultados_analiticos
for each row execute function public.agp_assert_linha_base_analise();

create or replace view public.agp_status_linhas_base as
select
  pp.id as participante_id,
  pp.projeto_id,
  pp.pessoa_id,
  p.nome,
  pe.legacy_perfil_atleta_id as atleta_id,
  lb.id as linha_base_id,
  coalesce(lb.status, 'ausente') as status,
  coalesce(lb.completude, 0) as completude,
  lb.data_referencia,
  public.agp_linha_base_vigente(pe.legacy_perfil_atleta_id, pp.projeto_id) as vigente
from public.agp_participantes_projeto pp
join public.agp_pessoas p on p.id = pp.pessoa_id
left join public.agp_perfis_esportivos pe on pe.pessoa_id = pp.pessoa_id
left join lateral (
  select x.* from public.agp_linhas_base_atleta x
  where x.atleta_id = pe.legacy_perfil_atleta_id and x.projeto_id = pp.projeto_id
  order by x.created_at desc limit 1
) lb on true
where pp.funcao_no_projeto = 'atleta' and pp.ativo;

grant select on public.agp_status_linhas_base to authenticated;
grant execute on function public.agp_linha_base_vigente(uuid, uuid) to authenticated;
grant execute on function public.agp_pode_analisar(uuid, uuid) to authenticated;

commit;
