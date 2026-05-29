from django.contrib import admin
from .models import (
    Student, LeaveRequest, Attendance, Department, 
    Subject, Timetable, Assignment, Exam, Result, 
    Circular, Notification, ParentProfile
)

class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ('student', 'from_date', 'to_date', 'status', 'created_at')
    list_filter = ('status', 'from_date')
    search_fields = ('student__name', 'student__roll_no')
    
    fieldsets = (
        ('Request Info', {'fields': ('student', 'reason', 'from_date', 'to_date', 'status')}),
        ('Mentor Review', {'fields': ('mentor_reviewed_by', 'mentor_reviewed_at', 'mentor_remark')}),
        ('CI Review', {'fields': ('class_incharge_reviewed_by', 'class_incharge_reviewed_at', 'class_incharge_remark')}),
    )

class TimetableAdmin(admin.ModelAdmin):
    list_display = ('batch', 'day', 'subject', 'start_time', 'teacher')
    list_filter = ('batch', 'day', 'department')

admin.site.register(Student)
admin.site.register(Department)
admin.site.register(Subject)
admin.site.register(Attendance)
admin.site.register(Timetable, TimetableAdmin)
admin.site.register(Assignment)
admin.site.register(Exam)
admin.site.register(Result)
admin.site.register(Circular)
admin.site.register(Notification)
admin.site.register(ParentProfile)
admin.site.register(LeaveRequest, LeaveRequestAdmin)