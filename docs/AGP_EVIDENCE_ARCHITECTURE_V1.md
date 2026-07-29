# AGP Evidence Architecture v1

## Product definition

AGP is a longitudinal, multidisciplinary sports intelligence platform for individual athletes, technical and medical commissions, clubs, associations and institutes. It must support the athlete from entry to exit, preserving age, category, growth, maturation, modality, competitive level, training history, professional evaluations, interventions and outcomes.

## Mandatory decision rule

No score, alert, recommendation, prediction or comparison may be emitted without:

1. identifiable source data;
2. collection instrument and version;
3. applicable protocol and version;
4. collector/respondent role;
5. collection timestamp;
6. completeness and reliability assessment;
7. reproducible calculation version;
8. explicit limitations;
9. scientific or institutional references when applicable;
10. professional validation for clinical or regulated conclusions.

When any minimum condition is absent, the AGP response is `dados_insuficientes`, never an invented recommendation.

## Evidence layers

1. Athlete self-report: daily questionnaires, pain, fatigue, sleep, recovery, wellbeing and perceived exertion.
2. Technical observation: execution quality, tactical/technical criteria, attendance and planned-versus-performed training.
3. Objective measurement: devices, laboratory, competition and standardized tests.
4. Professional assessment: medical, physiotherapy, psychology, nutrition, physical preparation and sport-specific evaluation.
5. Context: school, family, travel, competition, environment, social and institutional factors.
6. Scientific reference: validated articles, consensus statements, guidelines, protocols and standards.
7. Analytical result: versioned, explainable and auditable output derived only from the previous layers.

## Athlete longitudinal model

The athlete timeline must unite:

- chronological age and category;
- growth and maturation stage;
- anthropometry and biological changes;
- physical and physiological development;
- technical and tactical development;
- mental and psychological monitoring;
- recovery, sleep, pain and wellbeing;
- medical restrictions and professional documents;
- planned and executed training;
- interventions and observed response;
- individual and collective performance;
- competition and transition events;
- consent and legal responsibility for minors.

## Method evaluation

The AGP does not judge a coach through an arbitrary universal method. It compares:

- declared objective and hypothesis;
- planned stimulus;
- performed stimulus;
- athlete adherence;
- acute response;
- chronic response;
- individual baseline;
- applicable protocol ranges;
- comparable historical periods;
- similar groups only when methodological equivalence is valid;
- achieved result versus declared success criteria.

The output must distinguish association, inference and causality. Causal claims require adequate design and professional review.

## Integrative AI

The integrative AI is a controlled interpretation layer, not the source of truth. It must:

- retrieve only authorized internal athlete data;
- retrieve validated and versioned scientific sources;
- cite every external reference used;
- separate evidence, inference, hypothesis and recommendation;
- state confidence and limitations;
- identify conflicting evidence;
- refuse medical diagnosis;
- request professional validation when a conclusion exceeds the system's permitted scope;
- preserve model, prompt, source and output versions for audit.

## Execution gates

### Gate 1 — Evidence foundation
Database structures for protocols, instruments, collections, baselines, plans, sessions, interventions, professional documents, consent, scientific sources and analytical outputs.

### Gate 2 — Daily adherence
Real athlete questionnaire, expected schedule, missing/late responses, completeness, consistency and weekly/monthly adherence.

### Gate 3 — Multidimensional assessment
Versioned sport-specific instruments and professional roles, with no generic dimension values detached from observations.

### Gate 4 — Explainable engine
Scores and alerts built from valid collections, with input lineage, weights, thresholds, version, confidence and limitations.

### Gate 5 — Longitudinal response
Trend, variability, acute/chronic response, intervention effect and planned-versus-achieved comparison.

### Gate 6 — Multidisciplinary integration
Medical, technical, physical, physiological, psychological, nutritional, growth, maturation and collective views.

### Gate 7 — Scientific library
Validated sources linked to protocols and conclusions.

### Gate 8 — Integrative AI
Evidence-grounded interpretation with citations, confidence, conflict detection and professional validation.

### Gate 9 — Master homologation
Owner validates all flows with real controlled data.

### Gate 10 — Independent pilots
Two isolated technical environments compare methods, adherence, athlete response, operational limitations and system evolution.

## Current system constraint

The existing weighted-average engine is retained only as legacy experimental code. It must not be presented as validated AI or high-performance decision support until it is connected to evidence lineage, protocols, source validation and longitudinal data quality controls.
