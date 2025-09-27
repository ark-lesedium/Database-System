from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('student-dashboard/', views.student_dashboard_view, name='student_dashboard'),
    path('lecturer-dashboard/', views.lecturer_dashboard_view, name='lecturer_dashboard'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
]
