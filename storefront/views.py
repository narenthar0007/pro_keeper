from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.brand_scoping import get_request_brand
from accounts.ui_components import build_button, build_page_header
from accounts.ui_table import build_table

from storefront.decorators import storefront_manage_required
from storefront.forms import StorefrontForm, StorefrontProductForm
from storefront.models import OwnerStorefront, StorefrontProduct


@storefront_manage_required
def dashboard(request):
    qs = OwnerStorefront.objects.filter(owner=request.user)
    page_header = build_page_header(
        title='Business pages',
        subtitle='Create a simple e-commerce / showcase site for your brand',
        actions=[
            build_button('Create page', href=reverse('storefront_create'), variant='primary'),
        ],
    )
    rows = []
    for site in qs:
        pub = 'Live' if site.is_published else 'Draft'
        rows.append(
            {
                'name': site.business_name,
                'slug': site.slug,
                'status': pub,
                'url': site.public_url_path,
                'actions': (
                    f'<a href="{reverse("storefront_edit", args=[site.pk])}">Edit</a> · '
                    f'<a href="{site.public_url_path}" target="_blank" rel="noopener">View</a>'
                ),
            }
        )
    table = build_table(
        id='storefront-sites',
        columns=[
            {'key': 'name', 'label': 'Business'},
            {'key': 'slug', 'label': 'URL slug'},
            {'key': 'status', 'label': 'Status', 'badge': True},
            {'key': 'url', 'label': 'Path'},
            {'key': 'actions', 'label': '', 'html': True},
        ],
        rows=rows,
        empty_text='No business page yet. Create one to sell or showcase products online.',
    )
    return render(request, 'storefront/list_page.html', {'page_header': page_header, 'table': table})


@storefront_manage_required
def create(request):
    brand = get_request_brand(request)
    if request.method == 'POST':
        form = StorefrontForm(request.POST, request.FILES)
        if form.is_valid():
            site = form.save(commit=False)
            site.owner = request.user
            site.brand = brand
            site.save()
            messages.success(request, f'Business page created. Public URL: {site.public_url_path}')
            return redirect('storefront_edit', pk=site.pk)
    else:
        form = StorefrontForm()
    page_header = build_page_header(title='Create business page', subtitle='Your mini storefront on PropKeep')
    return render(request, 'storefront/form_page.html', {'page_header': page_header, 'form': form})


@storefront_manage_required
def edit(request, pk):
    site = get_object_or_404(OwnerStorefront, pk=pk, owner=request.user)
    products = site.products.all()
    if request.method == 'POST' and request.POST.get('action') == 'add_product':
        product_form = StorefrontProductForm(request.POST, request.FILES)
        if product_form.is_valid():
            product = product_form.save(commit=False)
            product.storefront = site
            product.save()
            messages.success(request, 'Product added.')
            return redirect('storefront_edit', pk=site.pk)
    else:
        product_form = StorefrontProductForm()

    if request.method == 'POST' and request.POST.get('action') != 'add_product':
        form = StorefrontForm(request.POST, request.FILES, instance=site)
        if form.is_valid():
            form.save()
            messages.success(request, 'Business page saved.')
            return redirect('storefront_dashboard')
    else:
        form = StorefrontForm(instance=site)

    page_header = build_page_header(
        title=site.business_name,
        subtitle=f'Public: {site.public_url_path}',
        actions=[
            build_button('Open live page', href=site.public_url_path, variant='secondary'),
        ],
    )
    return render(
        request,
        'storefront/edit.html',
        {
            'page_header': page_header,
            'form': form,
            'product_form': product_form,
            'products': products,
            'site': site,
        },
    )


def public_site(request, slug):
    site = get_object_or_404(
        OwnerStorefront.objects.select_related('brand'),
        slug=slug,
        is_published=True,
    )
    products = site.products.filter(is_active=True)
    show_login = not request.user.is_authenticated
    return render(
        request,
        'storefront/public.html',
        {
            'site': site,
            'products': products,
            'show_login': show_login,
            'login_url': reverse('login'),
            'platform_brand': site.platform_brand_name,
        },
    )
