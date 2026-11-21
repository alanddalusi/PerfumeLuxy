from django.urls import path
from . import views

app_name = 'home'

urlpatterns = [
    path("avisos/<str:kind>/confirmar/<str:token>/", views.confirm_notice, name="notice_confirm"),
    path("avisos/<str:kind>/baja/<str:token>/", views.unsubscribe_notice, name="notice_unsubscribe"),
    path("privacidad/", views.privacy, name="privacy"),
    path("sobre-nosotros/", views.about, name="about"),
    path("aviso-legal/", views.legal_notice, name="legal_notice"),
    path("politica-de-privacidad/", views.privacy_policy, name="privacy_policy"),
    path("contacto/", views.contact, name="contact"),
    path("", views.index, name="index"),
]
