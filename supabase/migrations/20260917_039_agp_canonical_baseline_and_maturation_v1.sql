begin;

alter table public.agp_linhas_base_atleta
  add column if not exists pessoa_id uuid references public.agp_pessoas(id) on delete set null,
  add column if not exists idade_calculada_em date,
  add column if not exists idade_calculo_metodo text,
  add column if not exists versao_maturacao text,
  add column if not exists competencia_codigo text references public.agp_competencias_canonicas(codigo) on delete restrict,
  add column if not exists credencial_verificada_no_registro boolean;

alter table public.agp_linhas_base_atleta
  alter column atleta_id drop not null;

update public.agp_linhas_base_atleta lb
set pessoa_id = pe.pessoa_id
from public.agp_perfis_esportivos pe
where pe.legacy_perfil_atleta_id = lb.atleta_id
  and pe.status = 'ativo'
  and lb.pessoa_id is null;

create or replace function public.agp_idade_decimal(p_data_nascimento date, p_data_referencia date)
returns numeric
language sql
immutable
strict
set search_path = public
as $$
  select round(((p_data_referencia - p_data_nascimento)::numeric / 365.2425), 6);
$$;

create index if not exists agp_linhas_base_pessoa_data_idx
  on public.agp_linhas_base_atleta(pessoa_id, data_referencia desc);

create or replace view public.agp_linhas_base_canonicas
with (security_invoker = true)
as
select
  lb.id,
  lb.pessoa_id,
  lb.participante_id,
  lb.projeto_id,
  lb.atleta_id as legacy_atleta_id,
  lb.categoria,
  lb.idade_cronologica,
  lb.idade_calculada_em,
  lb.idade_calculo_metodo,
  lb.sexo_registrado,
  lb.modalidade,
  lb.prova_posicao,
  lb.altura_cm,
  lb.massa_kg,
  lb.envergadura_cm,
  lb.altura_sentado_cm,
  lb.metodo_maturacional,
  lb.versao_maturacao,
  lb.offset_maturacional_anos,
  lb.idade_pico_velocidade_anos,
  lb.classificacao_maturacional,
  lb.maturacao_observacoes,
  lb.competencia_codigo,
  lb.credencial_verificada_no_registro,
  lb.data_referencia,
  lb.origem,
  lb.status,
  lb.completude,
  lb.created_at,
  lb.updated_at
from public.agp_linhas_base_atleta lb
where lb.pessoa_id is not null;

revoke all on public.agp_linhas_base_canonicas from public, anon, authenticated;
grant select on public.agp_linhas_base_canonicas to service_role;
grant execute on function public.agp_idade_decimal(date,date) to service_role;
revoke execute on function public.agp_idade_decimal(date,date) from public, anon, authenticated;

comment on function public.agp_idade_decimal(date,date) is
  'Calcula idade cronológica decimal pela diferença exata de dias/365.2425. Evita arredondamento prematuro antes de cálculos maturacionais.';

comment on column public.agp_linhas_base_atleta.versao_maturacao is
  'Versão explícita do método/equação maturacional utilizada no registro.';

commit;
