-- AGP Swimming: expose federative context through participant eligibility projection.

create or replace view public.agp_participantes_elegibilidade as
select
  pp.id as participante_id,
  pp.projeto_id,
  pp.pessoa_id,
  p.nome,
  p.data_nascimento,
  pp.funcao_no_projeto,
  pp.tecnico_responsavel_pessoa_id,
  public.agp_status_onboarding_participante(pp.id) as status_calculado,
  pp.status_onboarding as status_registrado,
  pp.ativo,
  pe.modalidade,
  pe.prova_posicao,
  pe.categoria,
  pe.nivel,
  pe.status_federativo,
  pe.federacao_nome,
  pe.registro_federativo
from public.agp_participantes_projeto pp
join public.agp_pessoas p on p.id = pp.pessoa_id
left join public.agp_perfis_esportivos pe
  on pe.pessoa_id = pp.pessoa_id
 and pe.status = 'ativo';

grant select on public.agp_participantes_elegibilidade to authenticated;

comment on view public.agp_participantes_elegibilidade is
  'Participant operational eligibility projection with sport and federative context. Federative status is contextual and does not independently determine event eligibility.';
