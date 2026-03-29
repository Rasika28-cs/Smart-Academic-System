from django.shortcuts import render, redirect

# Create your views here.
from django.contrib.auth.decorators import login_required
from .models import Event
from od.models import ODApplication

from django.contrib.auth.decorators import login_required

@login_required
def event_list(request):
    events = Event.objects.all()
    event_data = []

    for event in events:
        count = ODApplication.objects.filter(
            date=event.event_date, status='approved'
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

@login_required
def create_event(request):
    if request.method == 'POST':
        event_name = request.POST.get('event_name')
        college_name = request.POST.get('college_name')
        event_date = request.POST.get('event_date')
        brochure = request.FILES.get('brochure')  

        Event.objects.create(
            event_name=event_name,
            college_name=college_name,
            event_date=event_date,
            brochure=brochure,
            created_by=request.user  
        )

        return redirect('event_list')  # after creating event

    return render(request, 'od/create_event.html')