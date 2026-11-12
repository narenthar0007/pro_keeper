from django.urls import path

from storefront import views

urlpatterns = [
    path('', views.dashboard, name='storefront_dashboard'),
    path('create/', views.create, name='storefront_create'),
    path('<int:pk>/edit/', views.edit, name='storefront_edit'),
]
