from django.urls import path
from . import views

urlpatterns = [
    # Auth & Home
    path('', views.home, name='home'),
    path('login/', views.login_page, name='login_page'),
    path('logout/', views.logout_view, name='logout'),

    # Student Dash & Academic
    path('student/dashboard/', views.dashboard, name='student_dashboard'),
    path('student/attendance/', views.attendance, name='attendance'),
    path('student/leave-status/', views.leave_status, name='leave_status'),
    path('student/assignments/', views.assignment_list, name='student_assignments'),

    # Hierarchical Leave Chaining
    path('api/apply_leave/', views.apply_leave_api, name='apply_leave_api'),
    path('mentor/review/<int:leave_id>/<str:action>/', views.mentor_review_leave, name='mentor_review_leave'),
    path('ci/review/<int:leave_id>/<str:action>/', views.ci_review_leave, name='ci_review_leave'),

    # Role Dashboards
    path('mentor/dashboard/', views.mentor_dashboard, name='mentor_dashboard'),
    path('class-incharge/', views.ci_dashboard, name='class_incharge_dashboard'),
    path('hod/dashboard/', views.hod_dashboard, name='hod_dashboard'),

    # Analytics APIs
    path('api/stats/dashboard/', views.get_dashboard_stats, name='dashboard_stats'),
    path('notifications/unread/', views.get_notifications, name='get_notifications'),
]