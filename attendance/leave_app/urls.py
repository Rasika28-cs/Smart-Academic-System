from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [

    # =========================
    # HOME + AUTH
    # =========================
    path('', views.home, name='home'),
    path('auth/login/', views.login_page, name='login_page'),
    path('auth/logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_redirect, name='dashboard'),

    # =========================
    # STUDENT MODULE
    # =========================
    path('student/dashboard/', views.dashboard, name='student_dashboard'),
    path('student/attendance/', views.attendance, name='student_attendance'),
    path('student/leave-status/', views.leave_status, name='student_leave_status'),
    path('student/apply-leave/', views.apply_page, name='student_apply_leave'),
    path('student/defaulters/', views.student_defaulter_view, name='student_defaulters'),
    path('student/assignments/', views.assignment_list, name='student_assignments'),
    path('student/grades/', views.student_grades, name='student_grades'),

    # =========================
    # LEAVE MODULE (API + ACTIONS)
    # =========================
    path('api/leaves/apply/', views.apply_leave_api, name='apply_leave_api'),
    path('api/leaves/review/<int:leave_id>/', views.review_leave, name='review_leave'),

    # =========================
    # STAFF / ROLE DASHBOARDS
    # =========================
    path('mentor/dashboard/', views.mentor_dashboard, name='mentor_dashboard'),
    path('class-incharge/dashboard/', views.class_incharge_dashboard, name='class_incharge_dashboard'),
    path('teacher/dashboard/', views.teacher_dashboard, name='teacher_dashboard'),

    # =========================
    # HOD MODULE
    # =========================
    path('hod/dashboard/', views.hod_dashboard, name='hod_dashboard'),
    path('hod/reports/attendance/pdf/', views.attendance_report_pdf, name='attendance_report_pdf'),
    path('hod/reports/defaulters/pdf/', views.defaulter_report_pdf, name='defaulter_report_pdf'),

    # =========================
    # ATTENDANCE (TEACHER)
    # =========================
    path('teacher/attendance/mark/', views.mark_attendance, name='mark_attendance'),
    path('teacher/students/', views.view_students, name='view_students'),
    path('teacher/leaves/today/', views.today_leaves, name='today_leaves'),

    # =========================
    # UPLOADS
    # =========================
    path('upload/admissions/', views.upload_new_admissions, name='upload_new_admissions'),
    path('upload/defaulters/', views.upload_defaulters, name='upload_defaulters'),
    path('upload/grades/', views.upload_grades, name='upload_grades'),

    # =========================
    # DEFAULTERS MODULE
    # =========================
    path('defaulters/', views.defaulter_list, name='defaulter_list'),
    path('defaulters/update/<int:id>/', views.update_action, name='update_defaulter_action'),

    # =========================
    # NOTIFICATIONS
    # =========================
    path('notifications/', views.get_notifications, name='get_notifications'),
    path('notifications/read/<int:id>/', views.mark_as_read, name='mark_as_read'),
    path('notifications/read-all/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('notifications/delete/<int:id>/', views.delete_notification, name='delete_notification'),

    # =========================
    # CLASS REPRESENTATIVE (CR)
    # =========================
    path('cr/dashboard/', views.cr_dashboard, name='cr_dashboard'),

    # =========================
    # ASSIGNMENTS
    # =========================
    path('assignments/', views.manage_assignments, name='manage_assignments'),
    path('assignments/create/', views.create_assignment, name='create_assignment'),
    path('assignments/edit/<int:assignment_id>/', views.edit_assignment, name='edit_assignment'),
    path('assignments/delete/<int:assignment_id>/', views.delete_assignment, name='delete_assignment'),

    # =========================
    # TIMETABLE
    # =========================
    path('teacher/timetable/', views.view_timetable, name='view_timetable'),
    path('timetable/create/', views.create_timetable_entry, name='create_timetable_entry'),

    # =========================
    # PARENT PORTAL
    # =========================
    path('parent/login/', views.parent_login, name='parent_login'),
    path('parent/dashboard/', views.parent_dashboard, name='parent_dashboard'),

    # =========================
    # UTILITIES
    # =========================
    path('utils/calculator/', views.calculator, name='calculator'),
]

# =========================
# MEDIA FILES
# =========================
urlpatterns += static(
    settings.MEDIA_URL,
    document_root=settings.MEDIA_ROOT
)