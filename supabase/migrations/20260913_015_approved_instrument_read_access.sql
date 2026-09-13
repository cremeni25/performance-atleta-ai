begin;

drop policy if exists agp_instrumentos_authenticated_read on public.agp_instrumentos;
create policy agp_instrumentos_authenticated_read
on public.agp_instrumentos
for select
to authenticated
using (ativo = true and status_catalogo = 'aprovado');

commit;
