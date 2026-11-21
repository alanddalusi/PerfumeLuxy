from django.db import migrations

# Correct spelling of brand names shown on the storefront (db_name is the stable key).
NAMES = {"lancome": ("Lancome", "Lancôme"), "estee_lauder": ("Estee Lauder", "Estée Lauder")}


def forwards(apps, schema_editor):
    Brand = apps.get_model("products", "Brand")
    for code, (old, new) in NAMES.items():
        Brand.objects.filter(db_name=code, name=old).update(name=new)


def backwards(apps, schema_editor):
    Brand = apps.get_model("products", "Brand")
    for code, (old, new) in NAMES.items():
        Brand.objects.filter(db_name=code, name=new).update(name=old)


class Migration(migrations.Migration):
    dependencies = [("products", "0013_official_sizes")]
    operations = [migrations.RunPython(forwards, backwards)]
