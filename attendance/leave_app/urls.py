from django.urls import path
from . import views

urlpatterns = [

    # HOME
    path('', views.home, name='home'),
    path('login/', views.login_page, name='login_page'),
    path('logout/', views.logout_view, name='logout'),

    # ─────────────────────────────
    # STUDENT
    # ─────────────────────────────
    path('student/dashboard/', views.dashboard, name='student_dashboard'),

    path('student/apply/', views.apply_page, name='apply_page'),

    path(
        'student/attendance/',
        views.attendance,
        name='attendance'
    ),

    path(
        'student/leave-status/',
        views.leave_status,
        name='leave_status'
    ),

    path(
        'student/defaulter/',
        views.student_defaulter_view,
        name='student_defaulter'
    ),

    # ─────────────────────────────
    # CALCULATOR
    # ─────────────────────────────
    path(
        'calculator/',
        views.calculator,
        name='calculator'
    ),

    # ─────────────────────────────
    # TEACHER
    # ─────────────────────────────
    path(
        'teacher/dashboard/',
        views.teacher_dashboard,
        name='teacher_dashboard'
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
        'teacher/mark-attendance/',
        views.mark_attendance,
        name='mark_attendance'
    ),

    # ─────────────────────────────
    # MENTOR
    # ─────────────────────────────
    path(
        'mentor/dashboard/',
        views.mentor_dashboard,
        name='mentor_dashboard'
    ),

    path(
        'mentor/leaves/',
        views.mentor_leaves,
        name='mentor_leaves'
    ),

    path(
        'mentor/review/<int:leave_id>/<str:action>/',
        views.mentor_review_leave,
        name='mentor_review_leave'
    ),

    # ─────────────────────────────
    # CLASS INCHARGE
    # ─────────────────────────────
    path(
        'class-incharge/',
        views.class_incharge_dashboard,
        name='class_incharge_dashboard'
    ),

    path(
        'class-incharge/leaves/',
        views.ci_leaves,
        name='ci_leaves'
    ),

    path(
        'class-incharge/review/<int:leave_id>/<str:action>/',
        views.ci_review_leave,
        name='ci_review_leave'
    ),

    # ─────────────────────────────
    # HOD
    # ─────────────────────────────
    path(
        'hod/dashboard/',
        views.hod_dashboard,
        name='hod_dashboard'
    ),

    # ─────────────────────────────
    # LEAVE ACTIONS
    # ─────────────────────────────
    path(
        'leave/<int:leave_id>/<str:action>/',
        views.update_leave_status,
        name='update_leave_status'
    ),

    # ─────────────────────────────
    # APIs
    # ─────────────────────────────
    path(
        'api/apply_leave/',
        views.apply_leave_api,
        name='apply_leave_api'
    ),

    path(
        'upload-attendance/',
        views.upload_attendance,
        name='upload_attendance'
    ),

    # ─────────────────────────────
    # NOTIFICATIONS
    # ─────────────────────────────
    path(
        'notifications/count/',
        views.notification_count,
        name='notification_count'
    ),

    path(
        'notifications/',
        views.get_notifications,
        name='get_notifications'
    ),

    path(
        'notifications/read/<int:id>/',
        views.mark_as_read,
        name='mark_as_read'
    ),

    # ─────────────────────────────
    # DEFAULTERS
    # ─────────────────────────────
    path(
        'upload-defaulters/',
        views.upload_defaulters,
        name='upload_defaulters'
    ),

    path(
        'defaulters/',
        views.defaulter_list,
        name='defaulter_list'
    ),

    path(
        'update-action/<int:id>/',
        views.update_action,
        name='update_action'
    ),

]