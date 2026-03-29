from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import HttpResponse

from .models import ODApplication
from events.models import Event


# ─────────────────────────────────────────────
# APPLY OD
# ─────────────────────────────────────────────

@require_POST
@login_required
def apply_od(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    user = request.user

    # Prevent duplicate application on the same date
    already_applied = ODApplication.objects.filter(
        student=user,
        date=event.event_date
    ).exists()

    if already_applied:
        return redirect('event_list')

    # Auto-approve if fewer than 8 approved for that date
    count = ODApplication.objects.filter(
        date=event.event_date,
        status='approved'
    ).count()

    status = 'approved' if count < 8 else 'pending'

    ODApplication.objects.create(
        student=user,
        event=event,
        date=event.event_date,
        status=status,
    )

    return redirect('event_list')


# ─────────────────────────────────────────────
# STAFF PANEL (TEACHER)
# ─────────────────────────────────────────────

@login_required
def staff_panel(request):
    if not request.user.is_staff:
        return redirect('home')

    applications = ODApplication.objects.filter(status='pending').select_related('student', 'event')
    return render(request, 'od/staff.html', {'applications': applications})


# ─────────────────────────────────────────────
# APPROVE OD
# ─────────────────────────────────────────────

@require_POST
@login_required
def approve_od(request, id):
    if not request.user.is_staff:
        return HttpResponse('Unauthorized', status=403)

    app = get_object_or_404(ODApplication, id=id)
    app.status = 'approved'
    app.save()
    return redirect('staff_panel')


# ─────────────────────────────────────────────
# REJECT OD
# ─────────────────────────────────────────────

@require_POST
@login_required
def reject_od(request, id):
    if not request.user.is_staff:
        return HttpResponse('Unauthorized', status=403)

    app = get_object_or_404(ODApplication, id=id)
    app.status = 'rejected'
    app.save()
    return redirect('staff_panel')


# ─────────────────────────────────────────────
# OD DASHBOARD
# ─────────────────────────────────────────────

@login_required
def dashboard(request):
    return render(request, 'od/dashboard.html')
