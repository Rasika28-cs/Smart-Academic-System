from django.urls import path
from . import views

urlpatterns = [
    # Auth & Home
    path('', views.home, name='home'),
    path('login/', views.login_page, name='login_page'),
    path('logout/', views.logout_view, name='logout'),

    # Student
    path('student/dashboard/', views.dashboard, name='student_dashboard'),
    path('student/attendance/', views.attendance, name='attendance'),
    path('student/leave-status/', views.leave_status, name='leave_status'),
    path('student/apply/', views.apply_page, name='apply_page'),
    path('student/defaulter/', views.student_defaulter_view, name='student_defaulter'),
    path('student/assignments/', views.assignment_list, name='student_assignments'),

    # Utilities
    path('calculator/', views.calculator, name='calculator'),

    # Leave APIs
    path('api/apply_leave/', views.apply_leave_api, name='apply_leave_api'),
    path('mentor/review/<int:leave_id>/<str:action>/', views.mentor_review_leave, name='mentor_review_leave'),
    path('ci/review/<int:leave_id>/<str:action>/', views.ci_review_leave, name='ci_review_leave'),

    # Dashboards
    path('mentor/dashboard/', views.mentor_dashboard, name='mentor_dashboard'),
    path('class-incharge/', views.class_incharge_dashboard, name='class_incharge_dashboard'),
    path('hod/dashboard/', views.hod_dashboard, name='hod_dashboard'),
    path('teacher/dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
    path("dashboard/", views.dashboard_redirect, name="dashboard"),
    
    # Teacher Features
    path('teacher/mark-attendance/', views.mark_attendance, name='mark_attendance'),
    path('teacher/students/', views.view_students, name='view_students'),
    path('teacher/today-leaves/', views.today_leaves, name='today_leaves'),

    # Uploads
    path('upload/attendance/', views.upload_attendance, name='upload_attendance'),
    path('upload/defaulters/', views.upload_defaulters, name='upload_defaulters'),

    # Defaulters
    path('defaulters/', views.defaulter_list, name='defaulter_list'),

    # Notifications
    path('notifications/unread/', views.get_notifications, name='get_notifications'),
]