-- AGP security hardening v3 / canonical access helpers
-- Remove runtime trust in user-editable metadata for owner authorization.
-- Preserve SECURITY DEFINER helpers as intentional RLS primitives, but base them on canonical server-side records.

create table if not exists public.agp_governanca_plataforma (
  auth_id uuid primary key references auth.users(id) on delete restrict,
  pessoa_id uuid null references public.agp_pessoas(id) on delete set null,
  papel_codigo text not null default 'master_governance' references public.agp_papeis_canonicos(codigo) on delete restrict,
  status text not null default 'ativo' check (status in ('ativo','suspenso','revogado')),
  origem text not null default 'migracao_canonica',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

insert into public.agp_governanca_plataforma (auth_id,pessoa_id,papel_codigo,status,origem)
select
  u.id,
  ca.pessoa_id,
  'master_governance',
  'ativo',
  'owner_bootstrap_2026_09_16'
from auth.users u
left join public.agp_contas_acesso ca
  on ca.auth_id=u.id and ca.status='ativo'
where lower(coalesce(u.email,''))=lower('anderson@cremeni.com.br')
on conflict (auth_id) do update set
  pessoa_id=coalesce(excluded.pessoa_id,public.agp_governanca_plataforma.pessoa_id),
  papel_codigo='master_governance',
  status='ativo',
  updated_at=now();

alter table public.agp_governanca_plataforma enable row level security;
revoke all on public.agp_governanca_plataforma from public,anon,authenticated;
grant select,insert,update,delete on public.agp_governanca_plataforma to service_role;

create or replace function public.agp_is_owner()
returns boolean
language sql
stable
security definer
set search_path = public, auth
as $$
  select exists (
    select 1
    from public.agp_governanca_plataforma g
    where g.auth_id=auth.uid()
      and g.status='ativo'
      and g.papel_codigo='master_governance'
  );
$$;

create or replace function public.agp_has_institution_access(target uuid)
returns boolean
language sql
stable
security definer
set search_path = public, auth
as $$
  select public.agp_is_owner()
  or exists (
    select 1
    from public.agp_contas_acesso ca
    join public.agp_papeis_institucionais pi on pi.pessoa_id=ca.pessoa_id
    where ca.auth_id=auth.uid()
      and ca.status='ativo'
      and pi.instituicao_id=target
      and pi.status='ativo'
      and (pi.data_inicio is null or pi.data_inicio <= current_date)
      and (pi.data_fim is null or pi.data_fim >= current_date)
  )
  or exists (
    select 1
    from public.agp_contas_acesso ca
    join public.agp_participantes_projeto pp on pp.pessoa_id=ca.pessoa_id
    join public.agp_projetos_validacao pr on pr.id=pp.projeto_id
    where ca.auth_id=auth.uid()
      and ca.status='ativo'
      and pp.ativo=true
      and pr.instituicao_id=target
  )
  or exists (
    select 1
    from public.agp_membros_instituicao m
    where m.instituicao_id=target
      and m.auth_id=auth.uid()
      and m.ativo=true
      and (m.fim_acesso is null or m.fim_acesso > now())
  );
$$;

create or replace function public.agp_can_manage_institution(target uuid)
returns boolean
language sql
stable
security definer
set search_path = public, auth
as $$
  select public.agp_is_owner()
  or exists (
    select 1
    from public.agp_contas_acesso ca
    join public.agp_papeis_institucionais pi on pi.pessoa_id=ca.pessoa_id
    join public.agp_papel_capacidades pc on pc.papel_codigo=pi.papel_codigo and pc.ativo=true
    where ca.auth_id=auth.uid()
      and ca.status='ativo'
      and pi.instituicao_id=target
      and pi.status='ativo'
      and pc.capacidade_codigo in ('institution.people_manage','institution.project_manage')
      and (pi.data_inicio is null or pi.data_inicio <= current_date)
      and (pi.data_fim is null or pi.data_fim >= current_date)
  )
  or exists (
    select 1
    from public.agp_membros_instituicao m
    where m.instituicao_id=target
      and m.auth_id=auth.uid()
      and m.papel='admin_institucional'
      and m.ativo=true
  );
$$;

create or replace function public.agp_profissional_pode_projeto(p_projeto_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public, auth
as $$
  select public.agp_is_owner()
  or exists (
    select 1
    from public.agp_contas_acesso ca
    join public.agp_participantes_projeto pp on pp.pessoa_id=ca.pessoa_id
    join public.agp_papeis_canonicos papel on papel.codigo=pp.funcao_canonica_codigo
    join public.agp_papel_capacidades pc on pc.papel_codigo=papel.codigo and pc.ativo=true
    join public.agp_capacidades_canonicas cap on cap.codigo=pc.capacidade_codigo and cap.ativo=true
    where ca.auth_id=auth.uid()
      and ca.status='ativo'
      and pp.projeto_id=p_projeto_id
      and pp.ativo=true
      and papel.familia in ('equipe_tecnica','especialista')
      and cap.natureza in ('registrar','validar','decidir')
  )
  or exists (
    select 1
    from public.agp_projetos_validacao p
    join public.agp_membros_instituicao m on m.instituicao_id=p.instituicao_id
    where p.id=p_projeto_id
      and m.auth_id=auth.uid()
      and m.ativo=true
      and m.papel in ('admin_institucional','tecnico','treinador','preparador_fisico','medico','fisioterapeuta','psicologo','nutricionista','analista','assistente')
  );
$$;

-- These helpers are intentionally callable by authenticated because RLS policies compose them.
-- They expose only authorization booleans (or project->institution relation in the existing helper).
revoke execute on function public.agp_is_owner() from public,anon;
revoke execute on function public.agp_has_institution_access(uuid) from public,anon;
revoke execute on function public.agp_can_manage_institution(uuid) from public,anon;
revoke execute on function public.agp_profissional_pode_projeto(uuid) from public,anon;

grant execute on function public.agp_is_owner() to authenticated,service_role;
grant execute on function public.agp_has_institution_access(uuid) to authenticated,service_role;
grant execute on function public.agp_can_manage_institution(uuid) to authenticated,service_role;
grant execute on function public.agp_profissional_pode_projeto(uuid) to authenticated,service_role;

comment on function public.agp_is_owner() is
'Canonical platform-governance authorization. Does not trust user_metadata; checks server-side agp_governanca_plataforma for auth.uid().';
comment on function public.agp_profissional_pode_projeto(uuid) is
'RLS authorization primitive using canonical project role/capability with temporary legacy fallback during migration.';
