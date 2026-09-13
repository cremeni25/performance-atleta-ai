begin;

create policy agp_avaliacoes_profissionais_profissional_select
on public.agp_avaliacoes_profissionais
for select to authenticated
using (public.agp_profissional_pode_projeto(projeto_id));

create policy agp_avaliacoes_profissionais_profissional_insert
on public.agp_avaliacoes_profissionais
for insert to authenticated
with check (
  public.agp_profissional_pode_projeto(projeto_id)
  and profissional_auth_id = auth.uid()
);

create policy agp_respostas_intervencao_profissional_select
on public.agp_respostas_intervencao
for select to authenticated
using (public.agp_profissional_pode_projeto(projeto_id));

create policy agp_respostas_intervencao_profissional_insert
on public.agp_respostas_intervencao
for insert to authenticated
with check (
  public.agp_profissional_pode_projeto(projeto_id)
  and avaliado_por_auth_id = auth.uid()
);

create policy agp_validacoes_profissionais_profissional_select
on public.agp_validacoes_profissionais
for select to authenticated
using (
  exists (
    select 1
    from public.agp_resultados_analiticos r
    where r.id = resultado_id
      and public.agp_profissional_pode_projeto(r.projeto_id)
  )
);

create policy agp_validacoes_profissionais_profissional_insert
on public.agp_validacoes_profissionais
for insert to authenticated
with check (
  profissional_auth_id = auth.uid()
  and exists (
    select 1
    from public.agp_resultados_analiticos r
    where r.id = resultado_id
      and public.agp_profissional_pode_projeto(r.projeto_id)
  )
);

grant select, insert, update on public.agp_avaliacoes_profissionais to authenticated;
grant select, insert on public.agp_respostas_intervencao to authenticated;
grant select, insert on public.agp_validacoes_profissionais to authenticated;

commit;
