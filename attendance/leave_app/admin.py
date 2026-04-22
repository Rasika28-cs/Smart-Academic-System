from django.contrib import admin
from .models import Attendance, Student, LeaveRequest

# Actions
@admin.action(description="Mark selected as Approved")
def approve_leaves(modeladmin, request, queryset):
    queryset.update(status='Approved')

@admin.action(description="Mark selected as Rejected")
def reject_leaves(modeladmin, request, queryset):
    queryset.update(status='Rejected')


class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'from_date', 'to_date', 'status')
    list_filter = ('status',)
    actions = [approve_leaves, reject_leaves]   # ✅ IMPORTANT

admin.site.register(Student)
admin.site.register(LeaveRequest, LeaveRequestAdmin)
admin.site.register(Attendance)


from .models import DefaulterStudent

admin.site.register(DefaulterStudent)

