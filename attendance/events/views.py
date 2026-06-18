from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count

from .models import Event
from od.models import ODApplication
from leave_app.models import Student, Notification


# ─────────────────────────────────────────────
# EVENT LIST (OPTIMIZED)
# ─────────────────────────────────────────────

@login_required
def event_list(request):
    try:
        batch = request.user.student_profile.batch
    except AttributeError:
        raise PermissionDenied("Student profile not found")

    events = Event.objects.filter(batch=batch).order_by("-event_date")

    event_dates = [e.event_date for e in events]

    # Bulk fetch ODApplications (NO N+1)
    od_apps = ODApplication.objects.filter(date__in=event_dates)

    approved_counts = {}
    user_applied_dates = set()

    for app in od_apps:
        if app.status == "approved":
            approved_counts[app.date] = approved_counts.get(app.date, 0) + 1

        if app.student_id == request.user.id:
            user_applied_dates.add(app.date)

    event_data = [
        {
            "event": event,
            "count": approved_counts.get(event.event_date, 0),
            "applied": event.event_date in user_applied_dates,
        }
        for event in events
    ]

    return render(request, "od/events.html", {"event_data": event_data})


# ─────────────────────────────────────────────
# CREATE EVENT (SAFE)
# ─────────────────────────────────────────────

@login_required
def create_event(request):
    try:
        batch = request.user.student_profile.batch
    except AttributeError:
        raise PermissionDenied("Student profile not found")

    if request.method == "POST":
        event = Event.objects.create(
            event_name=request.POST.get("event_name"),
            college_name=request.POST.get("college_name"),
            event_date=request.POST.get("event_date"),
            brochure=request.FILES.get("brochure"),
            created_by=request.user,
            batch=batch,
        )

        students = Student.objects.filter(batch=batch).select_related("user")

        notification = Notification.objects.create(
            title="New OD Event Available",
            message=f"{event.event_name} at {event.college_name} on {event.event_date}",
            type="events",
            url="/events/events/",
        )

        notification.users.set([s.user for s in students if s.user])

        return redirect("event_list")

    return render(request, "od/create_event.html", {"batch": batch})


# ─────────────────────────────────────────────
# EDIT EVENT (SECURITY FIXED)
# ─────────────────────────────────────────────

@login_required
def edit_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)

    # 🔐 SECURITY: only creator or staff can edit
    if not (request.user == event.created_by or request.user.is_staff):
        raise PermissionDenied("Not allowed to edit this event")

    if request.method == "POST":
        event.event_name = request.POST.get("event_name")
        event.college_name = request.POST.get("college_name")
        event.event_date = request.POST.get("event_date")

        if request.FILES.get("brochure"):
            event.brochure = request.FILES["brochure"]

        event.save()
        return redirect("event_list")

    return render(request, "od/create_event.html", {
        "event": event,
        "edit_mode": True,
    })


# ─────────────────────────────────────────────
# DELETE EVENT (SECURE + POST ONLY)
# ─────────────────────────────────────────────

@login_required
def delete_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)

    # 🔐 SECURITY CHECK
    if not (request.user == event.created_by or request.user.is_staff):
        raise PermissionDenied("Not allowed to delete this event")

    if request.method == "POST":
        event.delete()
        return redirect("event_list")

    raise PermissionDenied("Invalid request method")