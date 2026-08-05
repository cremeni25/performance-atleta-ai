begin;

-- AGP-39 — Pipeline analítico versionado
-- Aplicar exclusivamente no projeto AGP: kvmtfngxkeodkqrxbjwo

create table if not exists public.agp_execucoes_analiticas (
  id uuid primary key default gen_random_uuid(),
  participante_id uuid not null references public.agp_participantes_projeto(id) on delete restrict,
  atleta_id uuid not null references public.perfis_atletas(id) on delete restrict,
  projeto_id uuid not null references public.agp_projetos_validacao(id) on delete restrict,
  tipo text not null default 'score_global',
  versao_motor text not null,
  status text not null default 'preparada' check (status in ('preparada','executando','concluida','falhou','cancelada')),
  parametros jsonb not null default '{}'::jsonb,
  resumo_entradas jsonb not null default '{}'::jsonb,
  resultado jsonb,
  explicacao text,
  limitacoes text,
  confianca numeric(5,2) check (confianca between 0 and 100),
  hash_execucao text,
  solicitado_por uuid,
  iniciado_em timestamptz,
  concluido_em timestamptz,
  erro text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.agp_execucao_entradas (
  execucao_id uuid not null references public.agp_execucoes_analiticas(id) on delete cascade,
  coleta_id uuid not null references public.agp_coletas(id) on delete restrict,
  versao_resposta_id uuid not null references public.agp_respostas_coleta_versoes(id) on delete restrict,
  dominio text not null,
  hash_entrada text not null,
  ordem integer not null default 0,
  created_at timestamptz not null default now(),
  primary key (execucao_id, coleta_id)
);

create unique index if not exists agp_execucoes_hash_idx
  on public.agp_execucoes_analiticas(hash_execucao)
  where hash_execucao is not null and status = 'concluida';

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
         or c.bloqueada_em is null
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

drop trigger if exists agp_execucao_analitica_gate on public.agp_execucoes_analiticas;
create trigger agp_execucao_analitica_gate
before insert or update on public.agp_execucoes_analiticas
for each row execute function public.agp_assert_execucao_analitica();

create or replace function public.agp_registrar_resultado_analitico()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if new.status = 'concluida' and old.status is distinct from 'concluida' then
    insert into public.agp_resultados_analiticos (
      atleta_id, projeto_id, tipo, versao_motor, janela_inicio, janela_fim,
      entradas, resultado, explicacao, confianca, limitacoes, status
    )
    select
      new.atleta_id,
      new.projeto_id,
      new.tipo,
      new.versao_motor,
      min(c.data_hora_coleta),
      max(c.data_hora_coleta),
      jsonb_agg(jsonb_build_object(
        'coleta_id', ei.coleta_id,
        'versao_resposta_id', ei.versao_resposta_id,
        'dominio', ei.dominio,
        'hash_entrada', ei.hash_entrada
      ) order by ei.ordem),
      new.resultado,
      coalesce(new.explicacao, 'Resultado produzido pelo pipeline analítico AGP.'),
      new.confianca,
      new.limitacoes,
      'preliminar'
    from public.agp_execucao_entradas ei
    join public.agp_coletas c on c.id = ei.coleta_id
    where ei.execucao_id = new.id;
  end if;
  return new;
end;
$$;

drop trigger if exists agp_execucao_resultado_sync on public.agp_execucoes_analiticas;
create trigger agp_execucao_resultado_sync
after update on public.agp_execucoes_analiticas
for each row execute function public.agp_registrar_resultado_analitico();

create or replace view public.agp_execucoes_analiticas_operacionais as
select
  e.*,
  p.nome as participante_nome,
  count(i.coleta_id) as total_entradas,
  coalesce(jsonb_agg(jsonb_build_object(
    'coleta_id', i.coleta_id,
    'versao_resposta_id', i.versao_resposta_id,
    'dominio', i.dominio,
    'hash_entrada', i.hash_entrada,
    'ordem', i.ordem
  ) order by i.ordem) filter (where i.coleta_id is not null), '[]'::jsonb) as entradas_detalhadas
from public.agp_execucoes_analiticas e
join public.agp_participantes_projeto pp on pp.id = e.participante_id
join public.agp_pessoas p on p.id = pp.pessoa_id
left join public.agp_execucao_entradas i on i.execucao_id = e.id
group by e.id, p.nome;

alter table public.agp_execucoes_analiticas enable row level security;
alter table public.agp_execucao_entradas enable row level security;

grant select on public.agp_execucoes_analiticas_operacionais to authenticated;

commit;
