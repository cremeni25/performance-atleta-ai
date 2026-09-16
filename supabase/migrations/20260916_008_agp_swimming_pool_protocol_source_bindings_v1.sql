-- AGP Swimming Pool V1 protocol scientific provenance.
-- Every canonical Swimming Pool protocol must have at least one scientific/regulatory source.

with x(protocolo_codigo,url) as (values
('SWM-PROT-DATA-QUALITY','https://pubmed.ncbi.nlm.nih.gov/37503541/'),
('SWM-PROT-GROWTH','https://pmc.ncbi.nlm.nih.gov/articles/PMC8481572/'),
('SWM-PROT-HEALTH','https://pubmed.ncbi.nlm.nih.gov/37515375/'),
('SWM-PROT-HEALTH','https://pubmed.ncbi.nlm.nih.gov/31935141/'),
('SWM-PROT-MEDLEY','https://pubmed.ncbi.nlm.nih.gov/22222324/'),
('SWM-PROT-MEDLEY','https://pubmed.ncbi.nlm.nih.gov/38815974/'),
('SWM-PROT-OVERWATER','https://pubmed.ncbi.nlm.nih.gov/36978699/'),
('SWM-PROT-OVERWATER','https://pubmed.ncbi.nlm.nih.gov/34372755/'),
('SWM-PROT-PHYSIOLOGY','https://pubmed.ncbi.nlm.nih.gov/19409842/'),
('SWM-PROT-PHYSIOLOGY','https://pubmed.ncbi.nlm.nih.gov/32767794/'),
('SWM-PROT-PSYCHOLOGY','https://pubmed.ncbi.nlm.nih.gov/16195023/'),
('SWM-PROT-PSYCHOLOGY','https://pubmed.ncbi.nlm.nih.gov/28682196/'),
('SWM-PROT-PSYCHOLOGY','https://pubmed.ncbi.nlm.nih.gov/29276857/'),
('SWM-PROT-PSYCHOLOGY','https://pubmed.ncbi.nlm.nih.gov/12081260/'),
('SWM-PROT-RACE-TIMING','https://www.worldaquatics.com/news/3090417/competition-regulations'),
('SWM-PROT-RACE-TIMING','https://pubmed.ncbi.nlm.nih.gov/29560605/'),
('SWM-PROT-RECOVERY','https://pubmed.ncbi.nlm.nih.gov/33564374/'),
('SWM-PROT-START','https://pubmed.ncbi.nlm.nih.gov/25555171/'),
('SWM-PROT-START','https://pubmed.ncbi.nlm.nih.gov/31493205/'),
('SWM-PROT-STRENGTH','https://pmc.ncbi.nlm.nih.gov/articles/PMC10797935/'),
('SWM-PROT-STRENGTH','https://pubmed.ncbi.nlm.nih.gov/31493205/'),
('SWM-PROT-STROKE-SPECIFIC','https://pubmed.ncbi.nlm.nih.gov/34372755/'),
('SWM-PROT-STROKE-SPECIFIC','https://pubmed.ncbi.nlm.nih.gov/36223481/'),
('SWM-PROT-STROKE-SPECIFIC','https://pubmed.ncbi.nlm.nih.gov/35674850/'),
('SWM-PROT-STROKE-SPECIFIC','https://pubmed.ncbi.nlm.nih.gov/39454553/'),
('SWM-PROT-STROKE-SPECIFIC','https://pubmed.ncbi.nlm.nih.gov/40483624/'),
('SWM-PROT-TRAINING-LOAD','https://pubmed.ncbi.nlm.nih.gov/32767794/'),
('SWM-PROT-TRAINING-LOAD','https://pubmed.ncbi.nlm.nih.gov/34814022/'),
('SWM-PROT-TRAINING-LOAD','https://pubmed.ncbi.nlm.nih.gov/19002069/'),
('SWM-PROT-TURN','https://pubmed.ncbi.nlm.nih.gov/29754533/'),
('SWM-PROT-TURN','https://pubmed.ncbi.nlm.nih.gov/30694108/'),
('SWM-PROT-UNDERWATER','https://pubmed.ncbi.nlm.nih.gov/35384796/')
)
insert into public.agp_protocolo_fontes(protocolo_id,fonte_id,justificativa)
select p.id,f.id,'Fonte científica/regulatória de sustentação do protocolo Swimming Pool V1.'
from x
join public.agp_protocolos p
  on p.codigo=x.protocolo_codigo and p.versao='1.0.0' and p.instituicao_id is null
join public.agp_fontes_cientificas f on f.url=x.url
on conflict do nothing;

create index if not exists idx_agp_protocolo_fontes_fonte
  on public.agp_protocolo_fontes(fonte_id);
create index if not exists idx_agp_metrica_fontes_fonte
  on public.agp_metrica_fontes(fonte_id);
create index if not exists idx_agp_perfil_metricas_metrica
  on public.agp_perfil_especializacao_metricas(metrica_id);
