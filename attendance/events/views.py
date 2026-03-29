from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

from .models import Event
from od.models import ODApplication


# ─────────────────────────────────────────────
# EVENT LIST
# ─────────────────────────────────────────────

@login_required
def event_list(request):
    events = Event.objects.all()
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
        Event.objects.create(
            event_name=request.POST.get('event_name'),
            college_name=request.POST.get('college_name'),
            event_date=request.POST.get('event_date'),
            brochure=request.FILES.get('brochure'),
            created_by=request.user,
        )
        return redirect('event_list')

    return render(request, 'od/create_event.html')
