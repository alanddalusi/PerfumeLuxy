# Adds the catalog origin and tags existing legacy fixture records as reference
# material. The data step only writes the new column: publication status,
# prices, stock and images are left untouched, and nothing is approved.

import json
from pathlib import Path

from django.db import migrations, models


LEGACY_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "products.json"


def tag_legacy_products(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    skus = [row["fields"]["sku"] for row in json.loads(LEGACY_FIXTURE.read_text(encoding="utf-8"))]
    for start in range(0, len(skus), 200):
        Product.objects.filter(sku__in=skus[start:start + 200]).update(catalog_origin="reference")


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0010_alter_product_options_product_publication_status_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='catalog_origin',
            field=models.CharField(choices=[('own', 'Catálogo propio'), ('reference', 'Referencia heredada')], db_index=True, default='own', help_text='Las fichas de referencia heredadas son informativas y nunca se pueden vender.', max_length=10, verbose_name='origen del catálogo'),
        ),
        migrations.RunPython(tag_legacy_products, migrations.RunPython.noop),
    ]
