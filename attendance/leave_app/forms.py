from django import forms
from .models import LeaveRequest, Assignment, Circular

class AssignmentUploadForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ['title', 'description', 'subject', 'batch', 'due_date', 'file']
        widgets = {'due_date': forms.DateTimeInput(attrs={'type': 'datetime-local'})}

class CircularForm(forms.ModelForm):
    class Meta:
        model = Circular
        fields = ['title', 'content', 'department', 'file']