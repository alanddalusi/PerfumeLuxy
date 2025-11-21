# 🚀 DEPLOYMENT GUIDE - Advanced Perfumery Features

## Cambios Subidos a GitHub ✅

**Commit:** `f30b8f4`  
**Branch:** `master`  
**Archivos:** 23 archivos | +5,085 líneas

---

## 📦 Lo que se ha implementado

### 🎯 Nuevos Modelos (6)
- **ProductSize** - Variantes de tamaño con badges, price/ml
- **ProductVideo** - Integración YouTube/Vimeo
- **SampleRequest** - Sistema completo de muestras gratis
- **UserFragranceProfile** - Perfil olfativo con recomendaciones
- **FragranceEvolution** - Timeline de evolución de notas
- **ProductComparison** - Guardar comparaciones de usuarios

### 🔧 Backend (13 vistas nuevas)
- Selector de tamaños (API JSON)
- Sistema de muestras (request, historial)
- Comparador de productos (hasta 3)
- Quiz de fragancias (6 preguntas)
- Perfil olfativo editable
- Notificaciones de stock
- Recomendaciones inteligentes

### 🎨 Frontend (12 templates nuevos)
- **Componentes:** size_selector, evolution_timeline, trust_badges, stars, wishlist_button, review_form, product_filters, related_products
- **Páginas:** compare, request_sample, my_samples, quiz_start, quiz_results

### 💎 Diseño Premium
- CSS con Playfair Display + Inter
- Paleta oro/blanco/negro
- Animaciones y efectos hover
- Grid responsivo

---

## 🔄 Pasos para Deployment en Producción

### 1. En el servidor (Heroku/Railway/etc):

```bash
# Pull últimos cambios
git pull origin master

# Activar entorno virtual
source venv/bin/activate  # o el comando correspondiente

# Instalar dependencias (si hay nuevas)
pip install -r requirements.txt

# Aplicar migraciones
python manage.py migrate

# Recolectar archivos estáticos
python manage.py collectstatic --noinput

# Reiniciar servidor
# (Heroku/Railway lo hace automáticamente con git push)
```

### 2. Variables de Entorno Requeridas:

Asegúrate de tener configuradas:
```
DEBUG=False
SECRET_KEY=<tu-clave-secreta-larga>
DATABASE_URL=<tu-url-postgresql>
ALLOWED_HOSTS=<tu-dominio.com>
AWS_ACCESS_KEY_ID=<tu-key>  # Si usas S3
AWS_SECRET_ACCESS_KEY=<tu-secret>
AWS_STORAGE_BUCKET_NAME=<tu-bucket>
```

### 3. Verificaciones Post-Deployment:

✅ **Migraciones aplicadas:**
```bash
python manage.py showmigrations products
# Debe mostrar [X] en 0009_fragranceevolution...
```

✅ **Admin accesible:**
- Navega a `/admin/`
- Verifica que aparecen los nuevos modelos:
  - Product Sizes
  - Product Videos
  - Sample Requests
  - User Fragrance Profiles
  - Fragrance Evolutions
  - Product Comparisons

✅ **URLs funcionando:**
- `/products/compare/` - Comparador
- `/products/quiz/` - Quiz de fragancias
- `/products/samples/request/<id>/` - Solicitar muestra
- `/products/samples/my-samples/` - Mis muestras
- `/products/profile/fragrance/` - Perfil olfativo

✅ **Archivos estáticos cargados:**
- Verifica que `luxury-premium.css` se carga
- Los iconos y fuentes (Playfair Display, Inter) funcionan

---

## 🎯 Próximos Pasos Recomendados

### A. Completar Integraciones

1. **Integrar componentes en product_detail:**
   ```html
   {% include 'includes/size_selector.html' %}
   {% include 'includes/evolution_timeline.html' with evolution=product.evolution %}
   {% include 'includes/trust_badges.html' %}
   ```

2. **Añadir filtros avanzados en all_products:**
   - Concentración (EDP/EDT/Parfum)
   - Duración (4-6h/6-8h/+8h)
   - Ocasión (diario/noche/formal)
   - Temporada (primavera/verano/otoño/invierno)

3. **Crear datos de ejemplo:**
   ```python
   # En Django admin, crear:
   - 3-4 tamaños por producto principal
   - 1 video de producto (YouTube)
   - 1 FragranceEvolution para bestsellers
   ```

### B. Testing

Probar flujos completos:
- [ ] Usuario solicita muestra → Admin aprueba → Marca como enviada
- [ ] Usuario completa quiz → Ve recomendaciones → Añade a wishlist
- [ ] Usuario compara 3 productos → Guarda comparación
- [ ] Usuario cambia tamaño → Precio actualiza → Añade a carrito

### C. SEO y Performance

- [ ] Añadir meta tags a nuevas páginas (quiz, compare)
- [ ] Optimizar imágenes de tamaños (WebP, lazy loading)
- [ ] Añadir Schema.org para videos de producto
- [ ] Crear sitemap entries para nuevas URLs

### D. Marketing

- [ ] Promocionar sistema de muestras gratis en home
- [ ] Email notification cuando muestra es aprobada
- [ ] Popup para invitar a hacer quiz en primera visita
- [ ] Badge "Nuevo" en productos con evolution timeline

---

## 📊 Métricas a Monitorear

Después del deployment, vigila:

1. **Conversión de muestras:** % solicitudes → compras
2. **Completación de quiz:** % usuarios que terminan las 6 preguntas
3. **Uso del comparador:** Promedio de productos comparados
4. **Engagement con tamaños:** % usuarios que cambian de tamaño
5. **Errores 500:** Monitorear logs por imports faltantes

---

## 🆘 Troubleshooting Común

### Error: "No module named 'models_extended'"
**Solución:** Verificar que existe `products/models_extended.py` y está en git

### Error: "relation products_productsize does not exist"
**Solución:** 
```bash
python manage.py migrate products --fake-initial
python manage.py migrate
```

### CSS no carga (luxury-premium.css)
**Solución:**
```bash
python manage.py collectstatic --clear --noinput
# Verificar STATIC_URL y STATIC_ROOT en settings
```

### Admin muestra "No such table"
**Solución:** Verificar que la migración 0009 se aplicó:
```bash
python manage.py showmigrations products
```

---

## 📞 Contacto

Si encuentras problemas durante el deployment:
1. Revisar logs del servidor (`heroku logs --tail` o similar)
2. Verificar que todas las variables de entorno están configuradas
3. Comprobar que PostgreSQL tiene espacio suficiente
4. Revisar permisos de archivos estáticos en S3/CDN

---

**Última actualización:** 21 Noviembre 2025  
**Versión:** 2.0.0 - Advanced Perfumery Features
