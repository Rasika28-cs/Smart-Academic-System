from django.contrib import admin
from .models import (
    Student, LeaveRequest, Attendance, Department,
    Subject, Timetable, Assignment,
    Notification, ParentProfile,
    DefaulterStudent,
    Absentee,
    LeaveAttendance
)

# -------------------------
# LEAVE REQUEST ADMIN
# -------------------------
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ('student', 'from_date', 'to_date', 'status', 'created_at')
    list_filter = ('status', 'from_date', 'to_date')
    search_fields = ('student__name', 'student__roll_no')

    fieldsets = (
        ('Request Info', {
            'fields': ('student', 'reason', 'from_date', 'to_date', 'status')
        }),
        ('Mentor Review', {
            'fields': ('mentor_reviewed_by', 'mentor_reviewed_at', 'mentor_remark')
        }),
    )

    ordering = ('-created_at',)


# -------------------------
# TIMETABLE ADMIN
# -------------------------
class TimetableAdmin(admin.ModelAdmin):
    list_display = ('batch', 'day', 'subject', 'start_time', 'teacher')
    list_filter = ('batch', 'day', 'department')
    search_fields = ('batch', 'subject__name', 'teacher')


# -------------------------
# ABSENTEE ADMIN
# -------------------------
class AbsenteeAdmin(admin.ModelAdmin):
    list_display = ('student', 'date')
    list_filter = ('date',)
    search_fields = ('student__name', 'student__roll_no')


# -------------------------
# LEAVE ATTENDANCE ADMIN
# -------------------------
class LeaveAttendanceAdmin(admin.ModelAdmin):
    list_display = ('leave_request', 'date')
    list_filter = ('date',)
    search_fields = ('leave_request__student__name',)


# -------------------------
# DEFAULT REGISTRATION
# -------------------------
admin.site.register(Student)
admin.site.register(Department)
admin.site.register(Subject)
admin.site.register(Attendance)
admin.site.register(Timetable, TimetableAdmin)
admin.site.register(Assignment)
admin.site.register(DefaulterStudent)
admin.site.register(Notification)
admin.site.register(ParentProfile)

admin.site.register(LeaveRequest, LeaveRequestAdmin)
admin.site.register(Absentee, AbsenteeAdmin)
admin.site.register(LeaveAttendance, LeaveAttendanceAdmin)