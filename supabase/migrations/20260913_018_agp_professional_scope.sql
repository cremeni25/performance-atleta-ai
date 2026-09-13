begin;

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
    from public.agp_projetos_validacao p
    join public.agp_membros_instituicao m on m.instituicao_id = p.instituicao_id
    where p.id = p_projeto_id
      and m.auth_id = auth.uid()
      and m.ativo is true
      and m.papel in ('admin_institucional','tecnico','treinador','preparador_fisico','medico','fisioterapeuta','psicologo','nutricionista','analista','assistente','observador')
  );
$$;

grant execute on function public.agp_profissional_pode_projeto(uuid) to authenticated;

commit;
