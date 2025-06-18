from django.urls import path
from . import views

urlpatterns = [
    path('', views.virtual_ta_api, name='virtual_ta_api'),
    path('health/', views.health_check, name='health_check'),

]
