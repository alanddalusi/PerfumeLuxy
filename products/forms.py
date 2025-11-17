from django import forms

from .widgets import CustomClearableFileInput
from .models import (
    Gender, Product, Category, Brand,
    Review, ReviewImage, PriceAlert, StockAlert
)


class ProductForm(forms.ModelForm):
    """
    Form that allows store owners/staff to add products to Eau Royal
    database
    """

    class Meta:
        model = Product
        fields = "__all__"

    image = forms.ImageField(
        label="Image", required=False, widget=CustomClearableFileInput
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        categories = Category.objects.all()
        brands = Brand.objects.all()
        genders = Gender.objects.all()
        category_names = [(c.id, c.get_friendly_name()) for c in categories]
        brand_names = [(b.id, b.get_friendly_name()) for b in brands]
        gender_names = [(g.id, g.get_friendly_name()) for g in genders]

        self.fields["category"].choices = category_names
        self.fields["brand"].choices = brand_names
        self.fields["gender"].choices = gender_names
        for field_name, field in self.fields.items():
            field.widget.attrs["class"] = "stripe-style-input"


class ReviewForm(forms.ModelForm):
    """Formulario para que los usuarios dejen reseñas"""
    
    class Meta:
        model = Review
        fields = ['rating', 'title', 'comment', 'skin_type', 'duration_experienced']
        widgets = {
            'rating': forms.RadioSelect(choices=[(i, str(i)) for i in range(1, 6)]),
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Título de tu reseña'
            }),
            'comment': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Cuéntanos tu experiencia con este perfume',
                'rows': 4
            }),
            'skin_type': forms.Select(attrs={'class': 'form-control'}),
            'duration_experienced': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 6-8 horas'
            }),
        }


class PriceAlertForm(forms.ModelForm):
    """Formulario para crear alertas de precio"""
    
    class Meta:
        model = PriceAlert
        fields = ['target_price']
        widgets = {
            'target_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Precio deseado (€)',
                'step': '0.01'
            })
        }


class StockAlertForm(forms.ModelForm):
    """Formulario para alertas de stock"""
    
    class Meta:
        model = StockAlert
        fields = ['email']
        widgets = {
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'tu@email.com'
            })
        }

