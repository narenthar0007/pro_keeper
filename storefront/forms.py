from django import forms

from storefront.models import OwnerStorefront, StorefrontProduct


class StorefrontForm(forms.ModelForm):
    class Meta:
        model = OwnerStorefront
        fields = [
            'business_name',
            'slug',
            'tagline',
            'about',
            'contact_email',
            'contact_phone',
            'theme_color',
            'logo',
            'hero_image',
            'hero_image_url',
            'is_published',
        ]
        widgets = {
            'about': forms.Textarea(attrs={'rows': 4}),
            'theme_color': forms.TextInput(attrs={'type': 'color'}),
            'slug': forms.TextInput(attrs={'placeholder': 'my-business'}),
        }


class StorefrontProductForm(forms.ModelForm):
    class Meta:
        model = StorefrontProduct
        fields = ['name', 'description', 'price', 'image', 'image_url', 'is_active', 'sort_order']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'price': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }
