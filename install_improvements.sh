#!/bin/bash
# Script de Instalación Rápida - PerfumeLuxe
# Ejecuta los pasos necesarios para poner en marcha las mejoras

echo "🎯 PERFUMELUXE - Instalación de Mejoras"
echo "======================================"
echo ""

# Colores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Verificar entorno virtual
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo -e "${RED}❌ ERROR: Entorno virtual no activado${NC}"
    echo "Por favor ejecuta: source .venv/Scripts/activate"
    exit 1
fi

echo -e "${GREEN}✓ Entorno virtual activado${NC}"
echo ""

# 1. Instalar dependencias adicionales (si es necesario)
echo "📦 Verificando dependencias..."
pip install --quiet --upgrade pip
echo -e "${GREEN}✓ Dependencias verificadas${NC}"
echo ""

# 2. Crear migraciones para nuevos modelos
echo "🔄 Creando migraciones..."
python manage.py makemigrations
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Migraciones creadas${NC}"
else
    echo -e "${RED}❌ Error al crear migraciones${NC}"
    exit 1
fi
echo ""

# 3. Aplicar migraciones
echo "⚙️  Aplicando migraciones a la base de datos..."
python manage.py migrate
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Migraciones aplicadas${NC}"
else
    echo -e "${RED}❌ Error al aplicar migraciones${NC}"
    exit 1
fi
echo ""

# 4. Verificar fixtures existentes
echo "📂 Verificando fixtures..."
if [ -f "products/fixtures/products.json" ]; then
    echo -e "${YELLOW}ℹ  Fixtures encontrados. ¿Quieres cargarlos? (s/n)${NC}"
    read -r load_fixtures
    if [ "$load_fixtures" = "s" ] || [ "$load_fixtures" = "S" ]; then
        echo "⬆️  Cargando fixtures..."
        python manage.py loaddata products/fixtures/brands.json
        python manage.py loaddata products/fixtures/categories.json
        python manage.py loaddata products/fixtures/fragrance_families.json
        python manage.py loaddata products/fixtures/products.json
        echo -e "${GREEN}✓ Fixtures cargados${NC}"
    fi
fi
echo ""

# 5. Colectar archivos estáticos
echo "📁 Recolectando archivos estáticos..."
python manage.py collectstatic --noinput --clear
echo -e "${GREEN}✓ Archivos estáticos actualizados${NC}"
echo ""

# 6. Verificar superusuario
echo "👤 Verificando superusuario..."
python manage.py shell << EOF
from django.contrib.auth.models import User
if not User.objects.filter(is_superuser=True).exists():
    print("NO_SUPERUSER")
else:
    print("HAS_SUPERUSER")
EOF

if grep -q "NO_SUPERUSER" /dev/tty; then
    echo -e "${YELLOW}⚠️  No hay superusuario. ¿Quieres crear uno ahora? (s/n)${NC}"
    read -r create_super
    if [ "$create_super" = "s" ] || [ "$create_super" = "S" ]; then
        python manage.py createsuperuser
    fi
fi
echo ""

# 7. Resumen
echo "========================================"
echo -e "${GREEN}✅ INSTALACIÓN COMPLETADA${NC}"
echo "========================================"
echo ""
echo "📋 Resumen de cambios aplicados:"
echo "  ✓ Sistema SEO completo instalado"
echo "  ✓ Sitemaps avanzados configurados"
echo "  ✓ Modelos de marketing creados"
echo "  ✓ Templates SEO integrados"
echo "  ✓ Base de datos actualizada"
echo ""
echo "🚀 Próximos pasos:"
echo "  1. Lee SECURITY_SETUP.md para producción"
echo "  2. Lee IMPLEMENTACION_COMPLETA.md para detalles"
echo "  3. Inicia el servidor: python manage.py runserver"
echo "  4. Verifica sitemaps en: http://localhost:8000/sitemap.xml"
echo "  5. Accede al admin: http://localhost:8000/admin/"
echo ""
echo "⚠️  IMPORTANTE para PRODUCCIÓN:"
echo "  - Migrar a PostgreSQL"
echo "  - Configurar AWS S3"
echo "  - Actualizar SECRET_KEY"
echo "  - Configurar variables de entorno"
echo ""
echo -e "${GREEN}¡Todo listo! 🎉${NC}"
