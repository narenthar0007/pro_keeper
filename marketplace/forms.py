from django import forms

from marketplace.models import MarketplaceListing


class MarketplaceListingForm(forms.ModelForm):
    class Meta:
        model = MarketplaceListing
        fields = [
            'kind',
            'title',
            'description',
            'city',
            'price',
            'price_label',
            'capacity_sqft',
            'contact_phone',
            'property_link',
            'image',
            'is_published',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, owner=None, properties_qs=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['property_link'].required = False
        if properties_qs is not None:
            self.fields['property_link'].queryset = properties_qs
        elif owner is not None:
            from properties.models import Property

            self.fields['property_link'].queryset = Property.objects.filter(owner=owner)
