from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='od_dashboard'),
    path('apply-od/<int:event_id>/', views.apply_od, name='apply_od'),
    path('staff/', views.staff_panel, name='staff_panel'),
    path('approve/<int:id>/', views.approve_od, name='approve_od'),
    path('reject/<int:id>/', views.reject_od, name='reject_od'),
]