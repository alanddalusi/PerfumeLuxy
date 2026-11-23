"""Editorial guides: original texts with internal links to verified product, note and family pages."""

GUIDES = [
    {"slug": "eau-de-parfum-o-eau-de-toilette", "template": "home/guides/concentrations.html",
     "title": "Eau de Parfum, Eau de Toilette, Parfum y colonia: diferencias",
     "description": "Qué significa cada concentración, qué es exactamente una colonia y cómo elegir entre Eau de Parfum y Eau de Toilette."},
    {"slug": "notas-de-salida-corazon-y-fondo", "template": "home/guides/notes.html",
     "title": "Notas de salida, corazón y fondo: cómo se lee un perfume",
     "description": "Qué es la pirámide olfativa, cuánto dura cada nivel y cómo usarla para elegir un perfume."},
    {"slug": "familias-olfativas", "template": "home/guides/families.html",
     "title": "Familias olfativas: floral, amaderada, ambarada, aromática y más",
     "description": "Las principales familias olfativas explicadas, con perfumes de ejemplo de cada una."},
    {"slug": "como-hacer-que-un-perfume-dure-mas", "template": "home/guides/longevity.html",
     "title": "Cómo hacer que un perfume dure más",
     "description": "Consejos prácticos para que tu perfume o colonia dure más en la piel y se conserve mejor en casa."},
]
BY_SLUG = {guide["slug"]: guide for guide in GUIDES}
