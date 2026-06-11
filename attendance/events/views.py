from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

from .models import Event
from od.models import ODApplication
from leave_app.models import Student
from leave_app.models import Notification

# ─────────────────────────────────────────────
# EVENT LIST
# ─────────────────────────────────────────────

@login_required
def event_list(request):
    events = Event.objects.filter(
        batch=request.user.student_profile.batch
    )
    event_data = []

    for event in events:
        count = ODApplication.objects.filter(
            date=event.event_date,
            status='approved'
        ).count()

        already_applied = ODApplication.objects.filter(
            student=request.user,
            date=event.event_date
        ).exists()

        event_data.append({
            'event': event,
            'count': count,
            'applied': already_applied,
        })

    return render(request, 'od/events.html', {'event_data': event_data})


# ─────────────────────────────────────────────
# CREATE EVENT
# ─────────────────────────────────────────────

@login_required
def create_event(request):
    if request.method == 'POST':

        event = Event.objects.create(
            event_name=request.POST.get('event_name'),
            college_name=request.POST.get('college_name'),
            event_date=request.POST.get('event_date'),
            brochure=request.FILES.get('brochure'),
            created_by=request.user,
            batch=request.user.student_profile.batch
        )

        students = Student.objects.filter(batch=event.batch)

        notification = Notification.objects.create(
            title="New OD Event Available",
            message=f"{event.event_name} at {event.college_name} on {event.event_date}",
            type="od",
            url="/od/events/"
        )

        notification.users.set(
            [student.user for student in students if student.user]
        )

        return redirect('event_list')

    return render(
        request,
        'od/create_event.html',
        {
            'batch': request.user.student_profile.batch
        }
    )