# AGP — Núcleo Canônico de Participantes V1

## Estado

Fase AGP-31 implementada em estrutura de banco, sem remoção de tabelas legadas.

## Objetivo

Separar definitivamente:

- identidade da pessoa;
- conta de autenticação;
- papel institucional;
- perfil esportivo;
- credencial profissional;
- responsável legal;
- participação em projeto;
- estado de onboarding;
- auditoria.

## Tabelas

- `agp_pessoas`
- `agp_contas_acesso`
- `agp_papeis_institucionais`
- `agp_perfis_esportivos`
- `agp_credenciais_profissionais`
- `agp_responsaveis_atleta`
- `agp_participantes_projeto`
- `agp_auditoria_participantes`

## Compatibilidade legada

`agp_perfis_esportivos.legacy_perfil_atleta_id` mantém a ponte controlada com `perfis_atletas` enquanto coletas, consentimentos e linhas de base ainda utilizam o identificador legado.

Nenhum registro legado é migrado automaticamente nesta versão. Essa decisão evita associação incorreta entre pessoas, contas Auth e atletas.

## Elegibilidade

A função `agp_status_onboarding_participante` retorna um dos estados:

- `rascunho`
- `perfil_pendente`
- `consentimento_pendente`
- `linha_base_pendente`
- `acesso_pendente`
- `apto_para_coleta`

A view `agp_participantes_elegibilidade` disponibiliza o estado calculado por participante e projeto.

## Segurança

- RLS habilitada em todas as novas tabelas.
- Proprietário mantém controle global por `agp_is_owner()`.
- Leitura institucional de participantes utiliza `agp_user_can_access_institution()` e `agp_project_institution_id()`.
- A migração não altera a precedência do proprietário.

## Aplicação

Executar somente no projeto Supabase AGP:

`kvmtfngxkeodkqrxbjwo`

Arquivo:

`supabase/migrations/20260805_004_agp_participant_core.sql`

Não executar no projeto CTI.

## Próxima evolução

Fase AGP-32:

1. serviço transacional de onboarding;
2. cadastro de pessoa e papel institucional;
3. vínculo explícito com projeto;
4. seleção explícita do técnico responsável;
5. registro auditável das alterações;
6. substituição gradual da seleção direta em `perfis_atletas`.
