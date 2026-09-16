# AGP — Documento Canônico Consolidado V1

**Projeto:** AGP Sports Intelligence — Algoritmo Global de Performance  
**Status:** CANÔNICO / CONGELADO PARA EXECUÇÃO  
**Data de consolidação:** 2026-09-16  
**Escopo:** definição de produto, arquitetura, papéis, ciência, especialização esportiva, internacionalização, governança e ordem obrigatória de construção.

---

## 1. Definição oficial do AGP

O AGP é um **sistema operacional longitudinal de desenvolvimento e decisão esportiva individual**, orientado por evidência, contexto, competência profissional, resposta a intervenção e aprendizado ao longo do tempo.

O AGP não é:

- um formulário;
- um simples sistema de cadastro;
- um score global;
- um sistema genérico que trata todos os esportes da mesma forma;
- um substituto do técnico ou do profissional especializado;
- um mecanismo de diagnóstico clínico autônomo;
- uma coleção de dashboards desconectados.

O ciclo canônico único do produto é:

**identidade → contexto → evidência → validação → interpretação → decisão → intervenção → resposta → aprendizado longitudinal**

Toda funcionalidade do AGP deve servir a esse ciclo.

---

## 2. Princípios congelados

### 2.1 Longitudinalidade

O atleta é acompanhado de forma contínua ao longo de dias, semanas, microciclos, mesociclos, temporadas e anos.

O histórico do atleta não reinicia por mudança de:

- clube;
- instituição;
- técnico;
- categoria;
- temporada;
- prova;
- posição;
- projeto;
- modalidade relacionada.

A memória longitudinal deve preservar crescimento, maturação, avaliações, treino, competição, intervenções, respostas, lesões/intercorrências, padrões de recuperação, progressão técnica e contexto.

### 2.2 Evidência antes de interpretação

Nenhuma interpretação, score, alerta, recomendação ou comparação pode ser considerada canônica sem rastreabilidade suficiente.

A evidência deve registrar, quando aplicável:

- origem;
- instrumento;
- versão;
- protocolo;
- respondente/coletor;
- data e hora;
- contexto;
- completude;
- confiabilidade;
- unidade;
- limitações;
- versão do cálculo;
- referência científica.

Quando a evidência for insuficiente, a saída correta é **dados insuficientes**, não inferência artificial.

### 2.3 Profissional não é substituído pela IA

O AGP apoia, organiza, cruza e contextualiza informação.

Decisões sensíveis ou dependentes de competência profissional exigem validação por pessoa habilitada no domínio correspondente.

### 2.4 Próxima ação

A experiência do usuário deve priorizar:

1. quem precisa de atenção;
2. por quê;
3. qual evidência sustenta a situação;
4. qual ação é permitida;
5. quem possui competência para executá-la.

O usuário não deve precisar navegar por múltiplos módulos para descobrir o que fazer.

### 2.5 Escala sem reconstrução

A expansão para novos esportes, países, idiomas, instituições e categorias não pode exigir reconstrução do Core.

A escala deverá ocorrer por especializações configuráveis e versionadas.

---

## 3. Arquitetura conceitual do produto

O AGP será organizado nos seguintes núcleos.

### 3.1 AGP Core

Responsável por funções universais:

- identidade;
- autenticação;
- papéis;
- vínculos;
- instituições;
- projetos;
- consentimento;
- elegibilidade;
- auditoria;
- evidências;
- protocolos;
- instrumentos;
- validação;
- intervenções;
- respostas;
- histórico longitudinal;
- segurança;
- internacionalização semântica;
- governança.

### 3.2 Sport Domain Profile — Perfil Canônico do Esporte

Cada esporte/modalidade deve possuir especialização própria e versionada.

Exemplos:

- `AGP-SWIMMING-POOL-V1`
- `AGP-FOOTBALL-V1`
- `AGP-VOLLEYBALL-INDOOR-V1`

O Sport Domain Profile não cria outro AGP. Ele adapta o mesmo Core às demandas reais do esporte.

Cada perfil esportivo deve conter, quando aplicável:

- ontologia e vocabulário do esporte;
- estrutura competitiva;
- estrutura de treinamento;
- papéis típicos;
- categorias;
- submodalidades;
- posições, provas ou funções;
- domínios de desempenho;
- métricas;
- unidades;
- protocolos;
- instrumentos;
- periodicidades;
- modelo de carga;
- modelo de recuperação;
- regras de interpretação;
- referências científicas;
- riscos e limitações;
- lógica de calendário;
- integrações externas relevantes;
- experiência de usuário específica.

### 3.3 Especialização interna

O AGP deve suportar a cadeia:

**AGP Core → esporte → modalidade → categoria → posição/prova/função → atleta individual**

Exemplos:

- Futebol → campo → sub-17 → atacante → atleta;
- Voleibol → quadra → adulto → levantador → atleta;
- Natação → piscina → juvenil → 100 m peito → atleta.

---

## 4. Papéis e competências

### 4.1 Regra principal

**Uma pessoa possui uma identidade única e pode acumular múltiplos papéis.**

O AGP não deve impor a regra “um usuário = um papel”.

### 4.2 Papéis canônicos

#### Atleta

Produz autopercepção, participa de coletas que lhe cabem, recebe retornos autorizados e acompanha sua evolução.

#### Equipe Técnica

Pode incluir, conforme o esporte e a instituição:

- técnico principal;
- técnico auxiliar;
- treinador específico;
- preparador físico;
- analista de desempenho;
- observador;
- demais funções esportivas técnicas.

Em estruturas menores, uma única pessoa pode acumular vários desses papéis.

#### Profissionais Especialistas

Incluem profissionais que atuam em domínios especializados, por exemplo:

- médico;
- fisioterapeuta;
- nutricionista;
- psicólogo;
- fisiologista;
- terapeuta;
- outros especialistas aplicáveis.

Cada especialista deve atuar dentro de seu escopo de competência.

#### Gestão Institucional

Responsável por estrutura, projetos, vínculos, recursos, equipes, visão agregada e governança local autorizada.

#### Master

Responsável pela governança da plataforma, ciência, segurança, integridade, catálogo, exceções e administração sistêmica.

O Master não deve executar rotineiramente o trabalho dos demais papéis em produção.

### 4.3 Comissão Técnica

“Comissão Técnica” não será tratada como identidade de usuário isolada.

Ela será uma **estrutura organizacional composta por pessoas e papéis técnicos e, quando aplicável, profissionais especialistas vinculados ao projeto/instituição**.

---

## 5. Internacionalização e pertencimento global

O AGP nasce global.

Internacionalização não será tratada como tradução posterior.

### 5.1 Princípio

**Nenhum idioma será estruturalmente secundário.**

O sistema manterá conceitos canônicos internos e apresentará linguagem localizada conforme:

- idioma;
- país/região;
- esporte;
- modalidade;
- papel do usuário;
- contexto profissional.

### 5.2 Localização semântica

O mesmo conceito interno pode ter diferentes representações locais.

Exemplo:

`head_coach`

- Brasil: Técnico principal
- Portugal: Treinador principal
- EUA: Head Coach
- Espanha: Entrenador principal

O banco e a inteligência permanecem consistentes.

### 5.3 Sport Profile + Locale Profile

A experiência final será determinada pela combinação entre:

- perfil do esporte;
- perfil de localidade/idioma.

A instituição deve sentir que o AGP foi criado para sua realidade esportiva e linguística.

### 5.4 Itens localizados

Devem ser localizáveis:

- textos de interface;
- terminologia esportiva;
- papéis;
- mensagens;
- relatórios;
- notificações;
- datas e horários;
- fusos;
- formatos numéricos;
- unidades de medida;
- categorias;
- consentimentos;
- textos legais aplicáveis;
- conteúdos científicos apresentados ao usuário.

### 5.5 Unidades

Valores devem ser armazenados em unidade canônica definida e convertidos na apresentação quando necessário.

### 5.6 Instrumentos científicos e idioma

O AGP deve diferenciar:

- idioma original do instrumento;
- tradução operacional;
- versão localizada;
- versão validada cientificamente;
- limitações de uso.

Uma simples tradução não poderá ser apresentada como instrumento clinicamente validado quando não houver validação correspondente.

---

## 6. Arquitetura científica

### 6.1 Protocolos

Protocolos devem possuir estrutura real, não apenas nome e descrição.

Quando aplicável, devem conter:

- objetivo;
- domínio;
- população;
- esporte/modalidade;
- categoria;
- método;
- instrumento;
- unidade;
- frequência;
- condições de aplicação;
- critérios;
- limites;
- interpretação;
- margem de erro/limitação;
- referências científicas;
- versão;
- status de aprovação.

### 6.2 Instrumentos

Instrumentos devem possuir:

- protocolo de origem;
- tipo;
- respondente;
- schema de campos;
- unidades;
- validações;
- regra de completude;
- periodicidade;
- versão;
- idioma/localização;
- status de aprovação;
- escopo de ativação.

### 6.3 Fontes científicas

O catálogo científico precisa ser populado e versionado.

Fontes devem ser vinculadas aos protocolos e interpretações onde aplicável.

### 6.4 Governança científica

Nenhuma regra científica nova deve entrar diretamente em produção sem:

1. fonte ou justificativa técnica;
2. definição de população aplicável;
3. limitações;
4. versão;
5. aprovação.

---

## 7. Inteligência e motor analítico

### 7.1 Pipeline

A arquitetura de pipeline rastreável deve ser preservada.

Entradas e resultados precisam manter hash, versão, origem, contexto, execução e explicação.

### 7.2 Motor ponderado atual

O motor baseado em médias por dimensão, pesos e classificação global é classificado como:

**LEGADO EXPERIMENTAL — NÃO CANÔNICO**

Ele pode permanecer temporariamente para comparação técnica, mas não deve representar a inteligência final do AGP nem sustentar sozinho decisões esportivas.

### 7.3 Motor canônico futuro

A inteligência canônica deve evoluir em camadas:

1. evidência validada;
2. normalização;
3. baseline individual;
4. regras científicas;
5. tendências e variabilidade;
6. integração multidisciplinar;
7. interpretação contextual;
8. recomendação assistida;
9. validação humana quando exigida.

### 7.4 Ordem das perguntas

Antes de um score, o AGP deve responder:

- o que aconteceu?
- mudou de verdade?
- comparado a quê?
- qual a qualidade da evidência?
- qual a confiança?
- qual contexto explica ou limita a leitura?
- quem precisa agir?

Scores só devem existir quando forem cientificamente defensáveis e úteis para a decisão.

---

## 8. Qualidade e cobertura de dados

O AGP deve tratar qualidade do dado como parte da inteligência.

Para cada interpretação relevante, deve ser possível conhecer:

- cobertura;
- completude;
- recência;
- confiabilidade;
- consistência;
- origem;
- outliers suspeitos;
- ausências relevantes;
- suficiência para aquela análise.

Mais dados não significam automaticamente melhor decisão.

---

## 9. Ciclos operacionais

### 9.1 Diário

Pode incluir:

- prontidão;
- sono;
- dor;
- fadiga;
- estresse;
- humor;
- RPE;
- sessão de treino;
- carga;
- intercorrências;
- decisão imediata.

### 9.2 Semanal / microciclo

Deve consolidar:

- carga;
- aderência;
- recuperação;
- sintomas;
- qualidade técnica;
- contexto;
- competição;
- necessidade de ajuste.

### 9.3 Mensal / mesociclo

Deve consolidar:

- testes;
- avaliações;
- evolução;
- intervenções;
- respostas;
- revisão de objetivo;
- maturação/crescimento quando aplicável.

### 9.4 Temporada

Deve organizar:

- objetivos;
- preparação;
- blocos;
- competições;
- recuperação;
- revisão;
- disponibilidade;
- histórico de resposta.

### 9.5 Longitudinal

Deve preservar a trajetória completa do atleta e aumentar progressivamente a capacidade de individualização.

---

## 10. Experiência por papel

### Atleta

Entrar → responder o que lhe cabe → executar orientações → receber retorno autorizado → acompanhar evolução.

### Equipe Técnica

Entrar → ver prioridades → registrar/acompanhar treino → observar execução → interpretar contexto → decidir/ajustar dentro de seu escopo.

### Profissional Especialista

Entrar → receber demandas de sua competência → avaliar → registrar evidência/restrições/recomendações → acompanhar resposta.

### Gestão Institucional

Entrar → acompanhar estrutura, grupos, projetos, atletas, recursos, pendências, evolução e indicadores agregados autorizados.

### Master

Entrar → governar identidades, papéis, ciência, integridade, segurança, catálogo, exceções e operação sistêmica.

---

## 11. Integrações externas

O AGP deve possuir arquitetura de conectores.

Sistemas e dispositivos externos devem ser tratados como **fontes de evidência**, não como dependências estruturais do Core.

No futuro, podem existir integrações com plataformas de wearables, GPS, força, biomecânica, saúde, vídeo, competição e sistemas especializados.

A ausência de uma integração específica nunca deverá exigir reconstrução do AGP.

---

## 12. Segurança e privacidade

Antes de piloto amplo, devem ser corrigidos e homologados:

- RLS;
- funções privilegiadas;
- views com privilégios especiais;
- políticas de acesso;
- isolamento institucional;
- princípio do menor privilégio;
- acesso por competência;
- tratamento de menores;
- consentimento;
- auditoria;
- retenção e exclusão quando aplicável.

Segurança não será adiada para depois da expansão.

---

## 13. Estado atual do sistema — leitura consolidada

### Preservar

- identidade canônica;
- estrutura de pessoa/conta/participação;
- consentimento;
- linha de base;
- elegibilidade;
- prontidão diária;
- sessões de treinamento;
- intervenções;
- respostas à intervenção;
- pipeline rastreável;
- catálogo de protocolos e instrumentos;
- auditoria;
- cockpit orientado por próxima ação.

### Corrigir / integrar

- múltiplos papéis por pessoa;
- separação entre equipe técnica e especialistas;
- comissão como estrutura, não usuário;
- competência por domínio;
- experiência operacional fora do Master;
- visão institucional;
- microciclo/mesociclo/temporada;
- idade decimal e maturação no motor;
- internacionalização semântica;
- especialização esportiva;
- conteúdo científico real;
- segurança.

### Legado / experimental

- motor de média ponderada como inteligência final;
- classificações globais não sustentadas por normas adequadas;
- endpoints/tabelas antigas que duplicam o Core;
- resíduos de Demo.

---

## 14. Primeiro pacote esportivo oficial

O primeiro Sport Domain Profile completo será:

**AGP Swimming Intelligence — Pool / Natação Piscina**

Ele será construído desde o início para localização semântica em:

- PT-BR;
- EN;
- ES.

A arquitetura não poderá impedir a inclusão posterior de outros idiomas.

O pacote de Natação Piscina deverá definir, no mínimo:

- terminologia;
- estilos;
- provas;
- distâncias;
- categorias;
- estrutura de treino;
- volume;
- intensidade;
- ritmo;
- séries;
- parciais;
- saída;
- virada;
- frequência/ciclo de braçada quando aplicável;
- indicadores físicos relevantes;
- recuperação;
- crescimento e maturação;
- competição;
- protocolos;
- instrumentos;
- referências científicas;
- UX específica.

---

## 15. Ordem obrigatória de construção

A sequência oficial é vinculante:

1. congelar este documento canônico;
2. incorporar o modelo de especialização esportiva ao modelo de dados;
3. incorporar internacionalização semântica ao Core;
4. corrigir papéis, competências e acúmulo de funções;
5. isolar legado e motor experimental do caminho canônico;
6. corrigir segurança crítica;
7. construir o Sport Domain Profile Natação Piscina V1;
8. ligar Natação Piscina ao ciclo operacional existente;
9. retomar homologação N1 exatamente do ponto interrompido;
10. provar o ciclo completo com dados controlados/reais adequados;
11. materializar microciclo, mesociclo e temporada;
12. ampliar inteligência institucional;
13. construir IA integrativa apenas sobre base governada;
14. escolher um segundo esporte para provar que a arquitetura escala sem reconstrução.

Não haverá caminhos paralelos que contradigam essa sequência sem autorização explícita.

---

## 16. Regras de execução

- não reconstruir o AGP do zero;
- não criar nova Demo como caminho alternativo;
- não multiplicar tabelas quando o Core existente puder ser evoluído;
- não apresentar dado simulado como solução final;
- não declarar funcionalidade pronta sem prova em runtime;
- não permitir que o Master seja o operador rotineiro dos demais papéis;
- não promover código legado a canônico por conveniência;
- não introduzir protocolo científico sem governança;
- não tratar novo esporte como simples valor de cadastro;
- não tratar i18n como mera tradução de strings;
- não expandir para novo esporte antes da validação do primeiro pacote completo.

---

## 17. Regra de governança do Chat / continuidade

Se, a qualquer momento, o processo de evolução:

- se desviar do cânone;
- introduzir diretrizes estruturais incompatíveis com decisões congeladas;
- perder coerência entre produto, ciência e arquitetura;
- iniciar caminhos paralelos não autorizados;
- deixar de distinguir canônico, legado e experimental;

então a evolução deve ser interrompida.

Antes de qualquer continuidade, deve ser produzido um **Documento Integral de Continuidade do AGP**, contendo sem omissões:

- propósito;
- decisões canônicas;
- arquitetura;
- papéis;
- infraestrutura;
- banco;
- repositórios;
- serviços;
- versões;
- dados controlados;
- homologações;
- pendências;
- riscos;
- itens legados;
- itens proibidos;
- estado da execução;
- próximo passo exato.

Esse documento deverá permitir a abertura de um novo chat sem perda de coerência ou direção.

---

## 18. Critério de pertencimento

Toda instituição deve perceber o AGP como uma solução profundamente dedicada ao seu esporte e à sua realidade.

O objetivo não é apenas funcionalidade. É produzir:

- confiança;
- parceria;
- seriedade;
- domínio da linguagem;
- domínio do esporte;
- resposta útil;
- valor percebido.

A instituição não deve sentir que está diante de “mais um software genérico para esporte”.

---

## 19. Critério de sucesso do produto

O AGP estará cumprindo sua proposta quando conseguir, de forma rastreável e especializada:

1. entender o contexto individual do atleta;
2. receber e qualificar evidências;
3. interpretar mudanças ao longo do tempo;
4. direcionar a pessoa competente;
5. registrar a decisão;
6. registrar a intervenção;
7. medir a resposta;
8. incorporar a resposta ao próximo ciclo;
9. aumentar progressivamente a individualização;
10. fazer isso em diferentes esportes, países e idiomas sem reconstruir o Core.

---

## 20. Status pós-consolidação

Com a aprovação deste documento:

- a fase conceitual deixa de ser aberta;
- o cânone passa a orientar código, banco, UX e ciência;
- mudanças estruturais relevantes exigem análise e autorização;
- a próxima frente de construção é o **modelo de dados do Motor de Especialização Esportiva + Internacionalização Semântica**, preservando o Core existente.
