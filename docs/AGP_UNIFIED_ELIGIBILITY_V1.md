# AGP — Elegibilidade Operacional Unificada v1

A elegibilidade de um atleta deixa de ser inferida por telas isoladas e passa a ser calculada por uma regra única no PostgreSQL.

## Aptidão para coleta

Exige participante ativo, perfil esportivo vinculado ao atleta legado, técnico responsável ativo no mesmo projeto, consentimento vigente e ao menos um instrumento ativo compatível.

## Aptidão para análise

Exige todos os requisitos de coleta e, adicionalmente, linha de base completa e vigente.

## Pendências padronizadas

- participante_inativo
- perfil_esportivo_pendente
- tecnico_responsavel_pendente
- tecnico_responsavel_invalido
- consentimento_pendente
- linha_base_pendente
- instrumento_indisponivel

## Interfaces públicas

- Função `agp_elegibilidade_operacional(participante_id)`
- View `agp_elegibilidade_operacional_projeto`
- `GET /api/v1/projetos/{projeto_id}/elegibilidade`
- `GET /api/v1/participantes/{participante_id}/elegibilidade`

A precedência Master governa a consulta administrativa. A regra não substitui os triggers de consentimento e linha de base; ela consolida o estado operacional usado pelas interfaces e pelos próximos fluxos de homologação.
