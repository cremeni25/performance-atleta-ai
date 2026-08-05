# AGP-40 — Validação profissional de resultados

A validação profissional sucede a execução analítica preliminar e não altera as evidências de entrada.

## Decisões

- `aprovado`: resultado passa a `validado`;
- `rejeitado`: resultado passa a `rejeitado`;
- `substituido`: resultado passa a `substituido` e exige referência ao resultado substituto.

## Visibilidade

A decisão define separadamente a visibilidade para atleta, comissão técnica e instituição. O perfil Master administra o registro, mas não transforma o resultado preliminar em parecer profissional sem decisão explícita e parecer técnico.

## Rastreabilidade

Cada decisão gera uma linha imutável em `agp_validacoes_profissionais`, preservando responsável, papel profissional, parecer, decisão, visibilidade e data.
