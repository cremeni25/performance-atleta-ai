# AGP — CONTEXTO DERIVADO E BAIXA FRICÇÃO OPERACIONAL V1

Status: CANÔNICO / PRINCÍPIO CONGELADO

## Regra central

O AGP deve preservar rastreabilidade profunda sem transformar rastreabilidade em burocracia para quem usa.

A pessoa informa apenas o conteúdo humano indispensável à ação. Identidade, projeto, participante, papel, competência, credencial e demais elementos já conhecidos pelo sistema devem ser resolvidos automaticamente a partir do contexto autenticado e do objeto sobre o qual a ação ocorre.

## Exemplo canônico — validação profissional

Entrada humana mínima:

**resultado → parecer → decisão**

Resolução automática do AGP:

**profissional autenticado → contexto do atleta → projeto → competência aplicável → credencial quando regulada → snapshot de auditoria**

Pessoa, participante, projeto, papel e credencial podem permanecer persistidos para rastreabilidade, mas não devem se transformar em campos repetitivos ou barreiras independentes de operação.

## Competência versus papel

O papel organiza a pessoa no contexto da equipe. A competência determina o escopo da ação profissional. Para autorizar uma ação, o AGP deve priorizar competência aplicável e, quando necessário, credencial regulada válida. O papel permanece como contexto e auditoria.

## Herança de contexto

Sempre que um objeto já conhece seu contexto, objetos derivados devem herdá-lo. Exemplos:

- uma validação herda atleta/participante/projeto do resultado;
- uma resposta herda atleta/contexto da intervenção;
- uma intervenção herda contexto da decisão quando criada a partir dela;
- uma evidência produzida em uma sessão herda participante/projeto/ciclo da sessão;
- uma avaliação profissional resolve identidade e escopo a partir do profissional autenticado e do participante alvo.

Duplicar contexto como exigência de entrada humana é proibido quando o sistema consegue derivá-lo de forma inequívoca.

## Segurança sem fricção

Baixa fricção não significa reduzir segurança. A autorização continua verificando vínculo, competência, credencial regulada e escopo. A diferença é que essa verificação ocorre internamente e produz uma única decisão de autorização.

## Regra de UX futura

A complexidade estrutural deve diminuir a complexidade percebida pelo usuário.

> Quanto maior a inteligência do AGP, menor deve parecer a complexidade para quem usa.

Este princípio vale para atleta, técnico, especialista, instituição e governança e deve orientar APIs, workflows e a interface final do Ponto Zero.
