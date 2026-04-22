from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_page, name='login_page'),
    path('signup/', views.signup_page, name='signup_page'),
    path('logout/', views.logout_view, name='logout'),

    # Student
    path('student/dashboard/', views.dashboard, name='student_dashboard'),
    path('student/apply/', views.apply_page, name='apply_page'),
    path('student/attendance/', views.attendance, name='attendance'),
    path('student/leave-status/', views.leave_status, name='leave_status'),
    path('calculator/', views.calculator, name='calculator'),

    # Teacher
    path('teacher/dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
    path('teacher/students/', views.view_students, name='view_students'),
    path('teacher/today-leaves/', views.today_leaves, name='today_leaves'),
    path('teacher/mark-attendance/', views.mark_attendance, name='mark_attendance'),

    # HOD
    path('hod/dashboard/', views.hod_dashboard, name='hod_dashboard'),

    # Leave actions
    path('leave/<int:leave_id>/<str:action>/', views.update_leave_status, name='update_leave_status'),

    # API
    path('api/apply_leave/', views.apply_leave_api, name='apply_leave_api'),
    path('upload-attendance/', views.upload_attendance, name='upload_attendance'),
    path('notifications/count/', views.notification_count, name='notification_count'),
    # urls.py

 path('notifications/', views.get_notifications, name='get_notifications'),
    path('notifications/read/<int:id>/', views.mark_as_read, name='mark_as_read'),
    path('upload-defaulters/', views.upload_defaulters, name='upload_defaulters'),
    path('defaulters/', views.defaulter_list, name='defaulter_list'),
    path('update-action/<int:id>/', views.update_action, name='update_action'),
    path('student/defaulter/', views.student_defaulter_view, name='student_defaulter'),
]