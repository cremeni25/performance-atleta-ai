begin;

-- Governança do núcleo de evidências.
-- O proprietário tem visão global; membros acessam somente dados de projetos/instituições vinculados.

create or replace function public.agp_project_institution(target_project uuid)
returns uuid
language sql
stable
security definer
set search_path = public
as $$
  select instituicao_id
  from public.agp_projetos_validacao
  where id = target_project;
$$;

create or replace function public.agp_athlete_project_access(target_athlete uuid, target_project uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select public.agp_is_owner()
  or exists (
    select 1
    from public.agp_atletas_projeto ap
    join public.agp_projetos_validacao p on p.id = ap.projeto_id
    where ap.atleta_id = target_athlete
      and ap.projeto_id = target_project
      and public.agp_has_institution_access(p.instituicao_id)
  );
$$;

-- Protocolos, instrumentos e fontes.
drop policy if exists agp_protocolos_read on public.agp_protocolos;
create policy agp_protocolos_read on public.agp_protocolos
for select using (
  public.agp_is_owner()
  or instituicao_id is null
  or public.agp_has_institution_access(instituicao_id)
);

drop policy if exists agp_protocolos_manage on public.agp_protocolos;
create policy agp_protocolos_manage on public.agp_protocolos
for all using (
  public.agp_is_owner()
  or (instituicao_id is not null and public.agp_can_manage_institution(instituicao_id))
) with check (
  public.agp_is_owner()
  or (instituicao_id is not null and public.agp_can_manage_institution(instituicao_id))
);

drop policy if exists agp_fontes_read on public.agp_fontes_cientificas;
create policy agp_fontes_read on public.agp_fontes_cientificas
for select using (public.agp_is_owner() or status_validacao = 'validada');

drop policy if exists agp_fontes_manage on public.agp_fontes_cientificas;
create policy agp_fontes_manage on public.agp_fontes_cientificas
for all using (public.agp_is_owner()) with check (public.agp_is_owner());

drop policy if exists agp_protocolo_fontes_read on public.agp_protocolo_fontes;
create policy agp_protocolo_fontes_read on public.agp_protocolo_fontes
for select using (true);

drop policy if exists agp_protocolo_fontes_manage on public.agp_protocolo_fontes;
create policy agp_protocolo_fontes_manage on public.agp_protocolo_fontes
for all using (public.agp_is_owner()) with check (public.agp_is_owner());

drop policy if exists agp_instrumentos_read on public.agp_instrumentos;
create policy agp_instrumentos_read on public.agp_instrumentos
for select using (
  public.agp_is_owner()
  or exists (
    select 1 from public.agp_protocolos p
    where p.id = protocolo_id
      and (p.instituicao_id is null or public.agp_has_institution_access(p.instituicao_id))
  )
);

drop policy if exists agp_instrumentos_manage on public.agp_instrumentos;
create policy agp_instrumentos_manage on public.agp_instrumentos
for all using (public.agp_is_owner()) with check (public.agp_is_owner());

-- Dados longitudinais por atleta/projeto.
drop policy if exists agp_linhas_base_access on public.agp_linhas_base_atleta;
create policy agp_linhas_base_access on public.agp_linhas_base_atleta
for all using (
  public.agp_is_owner()
  or (projeto_id is not null and public.agp_athlete_project_access(atleta_id, projeto_id))
) with check (
  public.agp_is_owner()
  or (projeto_id is not null and public.agp_athlete_project_access(atleta_id, projeto_id))
);

drop policy if exists agp_coletas_access on public.agp_coletas;
create policy agp_coletas_access on public.agp_coletas
for all using (
  public.agp_is_owner()
  or (projeto_id is not null and public.agp_athlete_project_access(atleta_id, projeto_id))
  or (origem = 'autodeclarado' and coletado_por_auth_id = auth.uid())
) with check (
  public.agp_is_owner()
  or (projeto_id is not null and public.agp_athlete_project_access(atleta_id, projeto_id))
  or (origem = 'autodeclarado' and coletado_por_auth_id = auth.uid())
);

drop policy if exists agp_planos_access on public.agp_planos_tecnicos;
create policy agp_planos_access on public.agp_planos_tecnicos
for all using (
  public.agp_is_owner()
  or (projeto_id is not null and public.agp_has_institution_access(public.agp_project_institution(projeto_id)))
) with check (
  public.agp_is_owner()
  or (projeto_id is not null and public.agp_can_manage_institution(public.agp_project_institution(projeto_id)))
);

drop policy if exists agp_sessoes_access on public.agp_sessoes_treinamento;
create policy agp_sessoes_access on public.agp_sessoes_treinamento
for all using (
  public.agp_is_owner()
  or exists (
    select 1 from public.agp_atletas_projeto ap
    join public.agp_projetos_validacao p on p.id = ap.projeto_id
    where ap.atleta_id = agp_sessoes_treinamento.atleta_id
      and public.agp_has_institution_access(p.instituicao_id)
  )
) with check (
  public.agp_is_owner()
  or exists (
    select 1 from public.agp_atletas_projeto ap
    join public.agp_projetos_validacao p on p.id = ap.projeto_id
    where ap.atleta_id = agp_sessoes_treinamento.atleta_id
      and public.agp_can_manage_institution(p.instituicao_id)
  )
);

drop policy if exists agp_intervencoes_access on public.agp_intervencoes;
create policy agp_intervencoes_access on public.agp_intervencoes
for all using (
  public.agp_is_owner()
  or (projeto_id is not null and public.agp_athlete_project_access(atleta_id, projeto_id))
) with check (
  public.agp_is_owner()
  or (projeto_id is not null and public.agp_athlete_project_access(atleta_id, projeto_id))
);

drop policy if exists agp_resultados_access on public.agp_resultados_analiticos;
create policy agp_resultados_access on public.agp_resultados_analiticos
for select using (
  public.agp_is_owner()
  or (projeto_id is not null and public.agp_athlete_project_access(atleta_id, projeto_id))
);

drop policy if exists agp_resultados_manage on public.agp_resultados_analiticos;
create policy agp_resultados_manage on public.agp_resultados_analiticos
for all using (public.agp_is_owner()) with check (public.agp_is_owner());

drop policy if exists agp_documentos_access on public.agp_documentos_profissionais;
create policy agp_documentos_access on public.agp_documentos_profissionais
for all using (
  public.agp_is_owner()
  or (projeto_id is not null and public.agp_athlete_project_access(atleta_id, projeto_id))
) with check (
  public.agp_is_owner()
  or (projeto_id is not null and public.agp_athlete_project_access(atleta_id, projeto_id))
);

drop policy if exists agp_consentimentos_access on public.agp_consentimentos;
create policy agp_consentimentos_access on public.agp_consentimentos
for select using (
  public.agp_is_owner()
  or responsavel_legal_auth_id = auth.uid()
  or exists (
    select 1 from public.perfis_atletas pa
    where pa.id = atleta_id and pa.auth_id = auth.uid()
  )
);

drop policy if exists agp_consentimentos_manage on public.agp_consentimentos;
create policy agp_consentimentos_manage on public.agp_consentimentos
for all using (public.agp_is_owner() or responsavel_legal_auth_id = auth.uid())
with check (public.agp_is_owner() or responsavel_legal_auth_id = auth.uid());

-- Instrumento inicial obrigatório: prontidão diária.
insert into public.agp_protocolos (
  instituicao_id, nome, dominio, modalidade, categoria, versao, objetivo,
  criterios, limites_interpretacao, ativo
)
select null, 'AGP Prontidão Diária', 'recuperacao', null, null, '1.0.0',
  'Registrar percepção diária do atleta sem produzir diagnóstico clínico automático.',
  '{"completude_minima":100,"janela_horas":24,"itens":["sono_horas","qualidade_sono","fadiga","dor","estresse","humor","rpe_ultima_sessao"]}'::jsonb,
  'Instrumento de monitoramento subjetivo. Não substitui avaliação médica, psicológica ou fisioterápica.',
  true
where not exists (
  select 1 from public.agp_protocolos
  where nome = 'AGP Prontidão Diária' and versao = '1.0.0' and instituicao_id is null
);

insert into public.agp_instrumentos (
  protocolo_id, nome, versao, tipo, respondente, periodicidade, schema_campos, regra_completude, ativo
)
select p.id, 'Questionário Diário de Prontidão AGP', '1.0.0', 'questionario', 'atleta', 'diaria',
  '{"sono_horas":{"tipo":"numero","min":0,"max":16},"qualidade_sono":{"tipo":"escala","min":1,"max":5},"fadiga":{"tipo":"escala","min":1,"max":5},"dor":{"tipo":"escala","min":0,"max":10},"estresse":{"tipo":"escala","min":1,"max":5},"humor":{"tipo":"escala","min":1,"max":5},"rpe_ultima_sessao":{"tipo":"escala","min":0,"max":10},"observacao":{"tipo":"texto","opcional":true}}'::jsonb,
  '{"campos_obrigatorios":["sono_horas","qualidade_sono","fadiga","dor","estresse","humor","rpe_ultima_sessao"],"percentual_minimo":100}'::jsonb,
  true
from public.agp_protocolos p
where p.nome = 'AGP Prontidão Diária' and p.versao = '1.0.0' and p.instituicao_id is null
  and not exists (
    select 1 from public.agp_instrumentos i
    where i.nome = 'Questionário Diário de Prontidão AGP' and i.versao = '1.0.0'
  );

create or replace view public.agp_adesao_questionario_diario as
select
  ap.projeto_id,
  ap.atleta_id,
  count(c.id) filter (
    where c.status in ('completa','validada')
      and c.data_hora_coleta >= now() - interval '7 days'
  ) as respostas_7d,
  round(
    least(100, count(c.id) filter (
      where c.status in ('completa','validada')
        and c.data_hora_coleta >= now() - interval '7 days'
    ) * 100.0 / 7), 1
  ) as adesao_7d_percentual,
  max(c.data_hora_coleta) as ultima_resposta
from public.agp_atletas_projeto ap
left join public.agp_coletas c
  on c.atleta_id = ap.atleta_id
 and c.projeto_id = ap.projeto_id
 and c.instrumento_id in (
   select id from public.agp_instrumentos
   where nome = 'Questionário Diário de Prontidão AGP' and versao = '1.0.0'
 )
group by ap.projeto_id, ap.atleta_id;

grant select on public.agp_adesao_questionario_diario to authenticated;

commit;
