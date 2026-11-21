"""Photo -> product remapping proposal (read-only). Rule found by visual inspection:
file SKU <= 0822: same SKU; 0823-0872: SKU + 2; 0873-0904: SKU + 3."""
import csv
import json
from pathlib import Path

products = json.load(open("products/fixtures/products.json", encoding="utf-8"))
brands = {b["pk"]: b["fields"]["name"] for b in json.load(open("products/fixtures/brands.json", encoding="utf-8"))}
by_sku = {p["fields"]["sku"]: p["fields"] for p in products}
ok = {  # visually checked: photo shows the product at the proposed SKU
    "0781", "0790", "0800", "0812", "0822", "0858", "0898", "0904", "0852", "0853", "0846", "0844", "0845", "0882",
    "0880", "0885", "0886", "0823", "0824", "0825", "0826", "0827", "0829", "0830", "0831", "0832", "0833", "0834",
    "0835", "0836", "0837", "0838", "0839", "0840", "0841", "0842", "0859", "0861", "0863", "0864", "0865", "0866",
    "0867", "0868", "0869", "0870", "0871", "0872", "0874", "0875", "0877", "0878",
}
mismatch = {
    "0828": "muestra 212 (frasco plateado, versión antigua), no '212 Vip'",
    "0860": "muestra Light Blue Eau Intense, no 'Light Blue'",
    "0862": "muestra Dolce Vita de Dior; la ficha heredada la atribuye a Dolce & Gabbana",
    "0873": "muestra Modern Muse EDP, no 'Modern Muse Chic'",
    "0876": "muestra Acqua di Giò pour homme, no 'Eau Pour Homme Reno'",
}


def offset(n):
    return 0 if n <= 822 else (2 if n <= 872 else 3)


rows = []
for path in sorted(Path("media").glob("ER117371*")):
    n = int(path.stem[-4:])
    target = f"ER117371{n + offset(n):04d}"
    product = by_sku.get(target)
    state = "mismatch" if path.stem[-4:] in mismatch else ("checked" if path.stem[-4:] in ok else "unchecked")
    rows.append([path.name, path.stem, offset(n), target, brands[product["brand"]] if product else "",
                 product["name"] if product else "(sin producto)", state, mismatch.get(path.stem[-4:], "")])
with open("auditorias/fotos-reasignacion.csv", "w", encoding="utf-8-sig", newline="") as handle:
    writer = csv.writer(handle)
    writer.writerow(["file", "file_sku", "offset", "proposed_product_sku", "brand", "name", "visual_check", "observation"])
    writer.writerows(rows)
from collections import Counter
print(len(rows), Counter(r[6] for r in rows), "sin producto:", sum(r[5] == "(sin producto)" for r in rows))
covered = {r[3] for r in rows if r[5] != "(sin producto)"}
print("productos con foto propuesta:", len(covered))
