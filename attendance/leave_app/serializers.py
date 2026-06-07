from rest_framework import serializers
from .models import Attendance, Result, LeaveRequest, Student



class AttendanceTrendSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attendance
        fields = ['date', 'status']

class LeaveWorkflowSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.name', read_only=True)
    class Meta:
        model = LeaveRequest
        fields = '__all__'