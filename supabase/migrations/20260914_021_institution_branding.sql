begin;

alter table public.agp_instituicoes
  add column if not exists nome_exibicao text,
  add column if not exists logo_url text,
  add column if not exists cor_primaria text,
  add column if not exists cor_secundaria text;

comment on column public.agp_instituicoes.nome_exibicao is 'Nome institucional exibido na experiência personalizada do AGP.';
comment on column public.agp_instituicoes.logo_url is 'URL ou data URI do logotipo institucional exibido pelo AGP.';
comment on column public.agp_instituicoes.cor_primaria is 'Cor institucional primária em formato hexadecimal.';
comment on column public.agp_instituicoes.cor_secundaria is 'Cor institucional secundária em formato hexadecimal.';

commit;
