from django.urls import path
from . import views

app_name = 'home'

urlpatterns = [
    path("avisos/<str:kind>/confirmar/<str:token>/", views.confirm_notice, name="notice_confirm"),
    path("avisos/<str:kind>/baja/<str:token>/", views.unsubscribe_notice, name="notice_unsubscribe"),
    path("privacidad/", views.privacy, name="privacy"),
    path("", views.index, name="index"),
]
