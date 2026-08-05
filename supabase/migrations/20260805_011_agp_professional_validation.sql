begin;

alter table public.agp_resultados_analiticos
  add column if not exists execucao_id uuid references public.agp_execucoes_analiticas(id) on delete set null,
  add column if not exists parecer_tecnico text,
  add column if not exists decisao_profissional text,
  add column if not exists papel_validador text,
  add column if not exists visivel_atleta boolean not null default false,
  add column if not exists visivel_comissao boolean not null default true,
  add column if not exists visivel_instituicao boolean not null default true,
  add column if not exists substitui_resultado_id uuid references public.agp_resultados_analiticos(id) on delete set null,
  add column if not exists motivo_substituicao text,
  add column if not exists updated_at timestamptz not null default now();

do $$ begin
  alter table public.agp_resultados_analiticos add constraint agp_resultados_decisao_check
  check (decisao_profissional is null or decisao_profissional in ('aprovado','rejeitado','substituido'));
exception when duplicate_object then null; end $$;

create table if not exists public.agp_validacoes_profissionais (
  id uuid primary key default gen_random_uuid(),
  resultado_id uuid not null references public.agp_resultados_analiticos(id) on delete cascade,
  decisao text not null check (decisao in ('aprovado','rejeitado','substituido')),
  parecer_tecnico text not null,
  papel_profissional text not null,
  profissional_auth_id uuid not null,
  visivel_atleta boolean not null default false,
  visivel_comissao boolean not null default true,
  visivel_instituicao boolean not null default true,
  substitui_resultado_id uuid references public.agp_resultados_analiticos(id) on delete set null,
  motivo_substituicao text,
  created_at timestamptz not null default now()
);

create index if not exists agp_validacoes_resultado_idx on public.agp_validacoes_profissionais(resultado_id, created_at desc);

create or replace function public.agp_aplicar_validacao_profissional()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  if new.decisao = 'substituido' and new.substitui_resultado_id is null then
    raise exception 'RESULTADO_SUBSTITUTO_OBRIGATORIO';
  end if;

  update public.agp_resultados_analiticos
     set status = case new.decisao when 'aprovado' then 'validado' when 'rejeitado' then 'rejeitado' else 'substituido' end,
         parecer_tecnico = new.parecer_tecnico,
         decisao_profissional = new.decisao,
         papel_validador = new.papel_profissional,
         validado_por_auth_id = new.profissional_auth_id,
         validado_em = new.created_at,
         visivel_atleta = new.visivel_atleta,
         visivel_comissao = new.visivel_comissao,
         visivel_instituicao = new.visivel_instituicao,
         substitui_resultado_id = new.substitui_resultado_id,
         motivo_substituicao = new.motivo_substituicao,
         updated_at = now()
   where id = new.resultado_id;
  return new;
end $$;

drop trigger if exists agp_validacoes_profissionais_apply on public.agp_validacoes_profissionais;
create trigger agp_validacoes_profissionais_apply
after insert on public.agp_validacoes_profissionais
for each row execute function public.agp_aplicar_validacao_profissional();

create or replace view public.agp_resultados_profissionais_operacionais as
select r.*, v.id as validacao_id, v.created_at as validado_profissionalmente_em
from public.agp_resultados_analiticos r
left join lateral (
  select * from public.agp_validacoes_profissionais x
  where x.resultado_id = r.id order by x.created_at desc limit 1
) v on true;

alter table public.agp_validacoes_profissionais enable row level security;

commit;
