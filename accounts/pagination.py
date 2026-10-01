from django.core.paginator import Paginator

PAGE_SIZE = 25


def paginate_table(request, queryset, page_size=PAGE_SIZE):
    """
    Paginate a queryset for table views.

    - Default: show one page of `page_size` rows (?page=1)
    - Load more: cumulative rows via ?thru=50, ?thru=75, ...
    """
    total = queryset.count()
    thru_raw = request.GET.get('thru')
    page_raw = request.GET.get('page')

    if thru_raw:
        try:
            thru = max(page_size, int(thru_raw))
        except (TypeError, ValueError):
            thru = page_size
        objects = list(queryset[:thru])
        showing = len(objects)
        has_more = total > showing
        current_page_number = max(1, (showing + page_size - 1) // page_size)
        paginator = Paginator(queryset, page_size)
        page = paginator.get_page(current_page_number)
        return {
            'object_list': objects,
            'page': page,
            'total': total,
            'showing': showing,
            'has_more': has_more,
            'next_thru': showing + page_size,
            'page_size': page_size,
            'is_cumulative': True,
        }

    paginator = Paginator(queryset, page_size)
    page = paginator.get_page(page_raw or 1)
    showing = page.end_index() if total else 0
    # For load-more from a numbered page, continue from end of this page
    next_thru = page.number * page_size
    if page.has_next():
        next_thru = page.number * page_size + page_size
    else:
        next_thru = showing

    return {
        'object_list': list(page.object_list),
        'page': page,
        'total': total,
        'showing': showing if page.number == 1 else len(page.object_list),
        'has_more': page.has_next(),
        'next_thru': page.number * page_size + page_size,
        'page_size': page_size,
        'is_cumulative': False,
    }


def pagination_query(request, **extra):
    """Build querystring preserving filters, applying extra params."""
    params = request.GET.copy()
    for key, value in extra.items():
        if value is None:
            params.pop(key, None)
        else:
            params[key] = value
    return params.urlencode()
