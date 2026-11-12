from django.urls import path

from marketplace import views

urlpatterns = [
    path('', views.browse, name='marketplace_browse'),
    path('my/', views.my_listings, name='marketplace_my_listings'),
    path('my/add/', views.listing_create, name='marketplace_listing_create'),
    path('my/<int:pk>/edit/', views.listing_edit, name='marketplace_listing_edit'),
]
