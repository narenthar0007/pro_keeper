from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.brand_scoping import get_request_brand
from accounts.privileges import is_admin_user
from accounts.ui_components import build_button, build_page_header
from accounts.ui_table import build_table

from marketplace.decorators import marketplace_manage_required
from marketplace.forms import MarketplaceListingForm
from marketplace.models import MarketplaceListing
from marketplace.services.feed import public_marketplace_feed


def _properties_qs(user):
    from properties.models import Property

    if is_admin_user(user):
        return Property.objects.all()
    return Property.objects.filter(owner=user)


@marketplace_manage_required
def my_listings(request):
    brand = get_request_brand(request)
    qs = MarketplaceListing.objects.filter(owner=request.user)
    if brand:
        qs = qs.filter(brand=brand)
    page_header = build_page_header(
        title='My marketplace listings',
        subtitle=f'{qs.count()} offers',
        actions=[
            build_button('Add listing', href=reverse('marketplace_listing_create'), variant='primary'),
            build_button('Browse marketplace', href=reverse('marketplace_browse'), variant='secondary'),
        ],
    )
    rows = [
        {
            'title': row.title,
            'kind': row.get_kind_display_short(),
            'city': row.city or '—',
            'published': 'Yes' if row.is_published else 'No',
            'actions': f'<a href="{reverse("marketplace_listing_edit", args=[row.pk])}">Edit</a>',
        }
        for row in qs[:100]
    ]
    table = build_table(
        id='marketplace-mine',
        columns=[
            {'key': 'title', 'label': 'Title'},
            {'key': 'kind', 'label': 'Type', 'badge': True},
            {'key': 'city', 'label': 'City'},
            {'key': 'published', 'label': 'Live', 'badge': True},
            {'key': 'actions', 'label': '', 'html': True},
        ],
        rows=rows,
        empty_text='No listings yet. Add products, services, skills, or construction capacity.',
    )
    return render(request, 'marketplace/list_page.html', {'page_header': page_header, 'table': table, 'kpis': None})


def browse(request):
    brand = get_request_brand(request)
    kind = (request.GET.get('kind') or '').strip()
    q = (request.GET.get('q') or '').strip()
    feed = public_marketplace_feed(brand, kind=kind or None, q=q)
    kind_choices = [
        ('', 'All types'),
        *list(MarketplaceListing.KIND_CHOICES),
        ('property_rent', 'Homes / units for rent'),
        ('property_sale', 'Homes / land for sale'),
    ]
    page_header = build_page_header(
        title='Marketplace',
        subtitle='Products, services, skills, construction, land, and property listings',
    )
    return render(
        request,
        'marketplace/browse.html',
        {
            'page_header': page_header,
            'feed': feed,
            'kind': kind,
            'q': q,
            'kind_choices': kind_choices,
        },
    )


@marketplace_manage_required
def listing_create(request):
    brand = get_request_brand(request)
    props = _properties_qs(request.user)
    if request.method == 'POST':
        form = MarketplaceListingForm(request.POST, request.FILES, owner=request.user, properties_qs=props)
        if form.is_valid():
            row = form.save(commit=False)
            row.owner = request.user
            row.brand = brand
            row.save()
            messages.success(request, 'Marketplace listing published.')
            return redirect('marketplace_my_listings')
    else:
        form = MarketplaceListingForm(owner=request.user, properties_qs=props)
    page_header = build_page_header(
        title='Add marketplace listing',
        subtitle='Sell products, offer services, showcase skills, or construction capacity',
    )
    return render(request, 'marketplace/form_page.html', {'page_header': page_header, 'form': form})


@marketplace_manage_required
def listing_edit(request, pk):
    row = get_object_or_404(MarketplaceListing, pk=pk, owner=request.user)
    props = _properties_qs(request.user)
    if request.method == 'POST':
        form = MarketplaceListingForm(
            request.POST,
            request.FILES,
            instance=row,
            owner=request.user,
            properties_qs=props,
        )
        if form.is_valid():
            form.save()
            messages.success(request, 'Listing updated.')
            return redirect('marketplace_my_listings')
    else:
        form = MarketplaceListingForm(instance=row, owner=request.user, properties_qs=props)
    page_header = build_page_header(title='Edit listing', subtitle=row.title)
    return render(request, 'marketplace/form_page.html', {'page_header': page_header, 'form': form})
