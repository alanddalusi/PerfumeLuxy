from django_countries import countries
from django_countries.widgets import CountrySelectWidget


class LuxuryCountryWidget(CountrySelectWidget):
    """
    Widget personalizado para el campo Country que evita el error
    BlankChoiceIterator
    """
    def __init__(self, attrs=None):
        super().__init__(attrs)
        # Forzar la evaluación de choices para evitar BlankChoiceIterator
        self.choices = list(countries)

    def build_attrs(self, base_attrs, extra_attrs=None):
        attrs = super().build_attrs(base_attrs, extra_attrs)
        attrs.update({
            'class': 'luxury-country-select stripe-style-input',
        })
        return attrs