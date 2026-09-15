from django import template

register = template.Library()


@register.inclusion_tag('web/erp/partials/_pagination.html', takes_context=True)
def pm_pagination(context, page_obj, window=2, param_name='page'):
    """
    Renderiza un control de paginación consistente (números + prev/next +
    "Mostrando X-Y de Z"), preservando automáticamente cualquier filtro
    activo en la querystring (todo lo que venga en GET, excepto el propio
    parámetro de página).

    `param_name` permite tener varios paginadores independientes en una
    misma pantalla (ej. ficha_trabajador: page_salarios, page_pagos, ...)
    sin que se pisen entre sí; por defecto sigue siendo 'page' para no
    romper las pantallas que ya usan este componente.
    """
    request = context.get('request')
    base_qs = ''
    if request is not None:
        params = request.GET.copy()
        params.pop(param_name, None)
        base_qs = params.urlencode()

    num_pages = page_obj.paginator.num_pages
    current = page_obj.number

    if num_pages <= 7:
        pages = list(range(1, num_pages + 1))
    else:
        pages = [1]
        start = max(2, current - window)
        end = min(num_pages - 1, current + window)
        if start > 2:
            pages.append(None)
        pages.extend(range(start, end + 1))
        if end < num_pages - 1:
            pages.append(None)
        pages.append(num_pages)

    return {
        'page_obj': page_obj,
        'pages': pages,
        'base_qs': base_qs,
        'param_name': param_name,
    }
