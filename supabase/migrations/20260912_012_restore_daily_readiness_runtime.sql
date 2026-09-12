begin;

insert into public.agp_protocolos (
  instituicao_id, codigo, nome, dominio, modalidade, categoria, versao, objetivo,
  criterios, limites_interpretacao, ativo, status_catalogo, aprovado_em
)
select
  null,
  'AGP-READINESS-DAILY',
  'AGP Prontidão Diária',
  'recuperacao',
  null,
  null,
  '1.0.0',
  'Monitorar diariamente sono, fadiga, dor, estresse, humor e esforço percebido para compor o contexto longitudinal do atleta sem produzir diagnóstico clínico automático.',
  '{"completude_minima":100,"janela_horas":24,"uso":"monitoramento_operacional"}'::jsonb,
  'Instrumento próprio de monitoramento subjetivo do AGP. Não substitui avaliação médica, psicológica, fisioterápica ou nutricional.',
  true,
  'aprovado',
  now()
where not exists (
  select 1 from public.agp_protocolos
  where codigo = 'AGP-READINESS-DAILY' and versao = '1.0.0'
);

insert into public.agp_instrumentos (
  protocolo_id, codigo, nome, descricao, versao, tipo, respondente, periodicidade,
  schema_campos, regra_completude, ativo, status_catalogo, aprovado_em
)
select
  p.id,
  'AGP-READINESS-DAILY-Q',
  'Questionário Diário de Prontidão AGP',
  'Registro diário de recuperação e percepção do atleta para leitura longitudinal individual.',
  '1.0.0',
  'questionario',
  'atleta',
  'diaria',
  '{"type":"object","required":["sono_horas","qualidade_sono","fadiga","dor","estresse","humor","rpe_ultima_sessao"],"properties":{"sono_horas":{"type":"number","title":"Horas de sono"},"qualidade_sono":{"type":"integer","title":"Qualidade do sono (1-5)","minimum":1,"maximum":5},"fadiga":{"type":"integer","title":"Fadiga percebida (1-5)","minimum":1,"maximum":5},"dor":{"type":"integer","title":"Dor/desconforto (0-10)","minimum":0,"maximum":10},"estresse":{"type":"integer","title":"Estresse percebido (1-5)","minimum":1,"maximum":5},"humor":{"type":"integer","title":"Humor percebido (1-5)","minimum":1,"maximum":5},"rpe_ultima_sessao":{"type":"integer","title":"Esforço percebido da última sessão (0-10)","minimum":0,"maximum":10},"observacao":{"type":"string","title":"Observação livre"}}}'::jsonb,
  '{"campos_obrigatorios":["sono_horas","qualidade_sono","fadiga","dor","estresse","humor","rpe_ultima_sessao"],"percentual_minimo":100}'::jsonb,
  true,
  'aprovado',
  now()
from public.agp_protocolos p
where p.codigo = 'AGP-READINESS-DAILY' and p.versao = '1.0.0'
  and not exists (
    select 1 from public.agp_instrumentos i
    where i.codigo = 'AGP-READINESS-DAILY-Q' and i.versao = '1.0.0'
  );

insert into public.agp_ativacoes_instrumentos (
  instrumento_id, instituicao_id, projeto_id, modalidade, categoria,
  versao_configuracao, obrigatorio, ordem, periodicidade_override,
  configuracao, data_inicio, ativo, aprovado_em
)
select
  i.id,
  p.instituicao_id,
  p.id,
  null,
  null,
  '1.0.0',
  true,
  10,
  'diaria',
  '{"origem":"catalogo_padrao_agp","uso":"prontidao_diaria"}'::jsonb,
  current_date,
  true,
  now()
from public.agp_instrumentos i
join public.agp_protocolos pr on pr.id = i.protocolo_id
cross join lateral (
  select pv.id, pv.instituicao_id
  from public.agp_projetos_validacao pv
  where pv.nome = 'Projeto Piloto AGP'
  order by pv.created_at asc
  limit 1
) p
where i.codigo = 'AGP-READINESS-DAILY-Q'
  and pr.codigo = 'AGP-READINESS-DAILY'
  and not exists (
    select 1 from public.agp_ativacoes_instrumentos ai
    where ai.instrumento_id = i.id and ai.projeto_id = p.id and ai.ativo = true
  );

commit;
