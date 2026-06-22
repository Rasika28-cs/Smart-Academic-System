from django.urls import path
from . import views

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [

    # ---------------- Home & Auth ----------------
    path('', views.home, name='home'),
    path('login/', views.login_page, name='login_page'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_redirect, name='dashboard'),

    # ---------------- Student ----------------
    path('student/dashboard/', views.dashboard, name='student_dashboard'),
    path('student/attendance/', views.attendance, name='attendance'),
    path('student/leave-status/', views.leave_status, name='leave_status'),
    path('student/apply/', views.apply_page, name='apply_page'),
    path('student/defaulter/', views.student_defaulter_view, name='student_defaulter'),
    path('student/assignments/', views.assignment_list, name='assignment_list'),
    path('student/grades/', views.student_grades, name='student_grades'),

    # ---------------- Leave ----------------
    path('api/apply-leave/', views.apply_leave_api, name='apply_leave_api'),
    path(
        'leave/review/<int:leave_id>/<str:action>/',
        views.review_leave,
        name='review_leave'
    ),

    # ---------------- Mentor / Staff ----------------
    path('mentor/dashboard/', views.mentor_dashboard, name='mentor_dashboard'),
    
    path('teacher/dashboard/', views.teacher_dashboard, name='teacher_dashboard'),

    # ---------------- HOD ----------------
    path('hod/dashboard/', views.hod_dashboard, name='hod_dashboard'),
    path(
        'hod/attendance-report-pdf/',
        views.attendance_report_pdf,
        name='attendance_report_pdf'
    ),
    path(
        'hod/defaulter-report-pdf/',
        views.defaulter_report_pdf,
        name='defaulter_report_pdf'
    ),

    # ---------------- Attendance ----------------
    path(
        'teacher/mark-attendance/',
        views.mark_attendance,
        name='mark_attendance'
    ),
    path(
        'teacher/students/',
        views.view_students,
        name='view_students'
    ),
    path(
        'teacher/today-leaves/',
        views.today_leaves,
        name='today_leaves'
    ),

   
    path(
        'upload/defaulters/',
        views.upload_defaulters,
        name='upload_defaulters'
    ),
    path(
        'upload/grades/',
        views.upload_grades,
        name='upload_grades'
    ),

    # ---------------- Defaulters ----------------
    path(
        'defaulters/',
        views.defaulter_list,
        name='defaulter_list'
    ),
    path(
        'defaulters/update-action/<int:id>/',
        views.update_action,
        name='update_action'
    ),

    # ---------------- Notifications ----------------
    path(
        'notifications/unread/',
        views.get_notifications,
        name='get_notifications'
    ),
    path(
        'notifications/read/<int:id>/',
        views.mark_as_read,
        name='mark_as_read'
    ),
    path(
        'notifications/read-all/',
        views.mark_all_notifications_read,
        name='mark_all_notifications_read'
    ),
    path(
        'notifications/delete/<int:id>/',
        views.delete_notification,
        name='delete_notification'
    ),

    # ---------------- Class Representative ----------------
    path('cr/dashboard/', views.cr_dashboard, name='cr_dashboard'),
    path(
        'assignments/manage/',
        views.manage_assignments,
        name='manage_assignments'
    ),
    path(
        'assignments/create/',
        views.create_assignment,
        name='create_assignment'
    ),
    path(
        'assignments/edit/<int:assignment_id>/',
        views.edit_assignment,
        name='edit_assignment'
    ),
    path(
        'assignments/delete/<int:assignment_id>/',
        views.delete_assignment,
        name='delete_assignment'
    ),

    # ---------------- Timetable ----------------
    path(
        'teacher/timetable/',
        views.view_timetable,
        name='view_timetable'
    ),
    path(
        'timetable/create/',
        views.create_timetable_entry,
        name='create_timetable_entry'
    ),

    # ---------------- Parent Portal ----------------
    path('parent/login/', views.parent_login, name='parent_login'),
    path(
        'parent/dashboard/',
        views.parent_dashboard,
        name='parent_dashboard'
    ),

    # ---------------- Utilities ----------------
    path('calculator/', views.calculator, name='calculator'),
]

urlpatterns += static(
    settings.MEDIA_URL,
    document_root=settings.MEDIA_ROOT
)