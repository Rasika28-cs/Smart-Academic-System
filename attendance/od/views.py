from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.core.exceptions import PermissionDenied
from django.urls import reverse

from leave_app.models import Notification, Student
from django.contrib.auth.models import User
from .models import ODApplication
from events.models import Event


# ─────────────────────────────────────────────
# OD STATUS
# ─────────────────────────────────────────────

@login_required
def view_od_status(request):
    try:
        student = request.user.student_profile
    except AttributeError:
        raise PermissionDenied("Student profile not found")

    ods = ODApplication.objects.filter(student=student).select_related("event")

    return render(request, "od/od_status.html", {"ods": ods})


# ─────────────────────────────────────────────
# APPLY OD
# ─────────────────────────────────────────────

@require_POST
@login_required
def apply_od(request, event_id):
    try:
        student = request.user.student_profile
    except AttributeError:
        raise PermissionDenied("Student profile not found")

    event = get_object_or_404(Event, id=event_id)

    # Prevent duplicate application
    if ODApplication.objects.filter(student=student, event=event).exists():
        return redirect("event_list")

    approved_count = ODApplication.objects.filter(
        date=event.event_date,
        status="approved"
    ).count()

    status = "approved" if approved_count < 8 else "pending"

    od = ODApplication.objects.create(
        student=student,
        event=event,
        date=event.event_date,
        status=status,
    )

    # Notify staff
    staff_users = User.objects.filter(is_staff=True)

    notif = Notification.objects.create(
        title="New OD Request",
        message=f"{request.user.username} applied for OD: {event.event_name}",
        type="od",
        url=reverse("staff_panel"),
    )

    notif.users.set(staff_users)

    return redirect("event_list")


# ─────────────────────────────────────────────
# STAFF PANEL
# ─────────────────────────────────────────────

@login_required
def staff_panel(request):
    if not request.user.is_staff:
        raise PermissionDenied("Only staff allowed")

    batch = request.GET.get("batch")

    applications = ODApplication.objects.filter(
        status="pending"
    ).select_related("student", "event")

    if batch:
        applications = applications.filter(student__batch=batch)

    return render(request, "od/staff.html", {
        "applications": applications,
        "batches": Student.objects.values_list(
            "batch", flat=True
        ).distinct().order_by("batch"),
        "selected_batch": batch,
    })


# ─────────────────────────────────────────────
# APPROVE OD
# ─────────────────────────────────────────────

@require_POST
@login_required
def approve_od(request, id):
    if not request.user.is_staff:
        raise PermissionDenied("Unauthorized")

    app = get_object_or_404(ODApplication, id=id)

    if app.status != "pending":
        return redirect("staff_panel")

    app.status = "approved"
    app.save()

    notif = Notification.objects.create(
        title="OD Approved",
        message=f"Your OD request for {app.event.event_name} has been approved.",
        type="od",
        url=reverse("view_od_status"),
    )

    notif.users.add(app.student.user)

    return redirect("staff_panel")


# ─────────────────────────────────────────────
# REJECT OD
# ─────────────────────────────────────────────

@require_POST
@login_required
def reject_od(request, id):
    if not request.user.is_staff:
        raise PermissionDenied("Unauthorized")

    app = get_object_or_404(ODApplication, id=id)

    if app.status != "pending":
        return redirect("staff_panel")

    app.status = "rejected"
    app.save()

    notif = Notification.objects.create(
        title="OD Rejected",
        message=f"Your OD request for {app.event.event_name} has been rejected.",
        type="od",
        url=reverse("view_od_status"),
    )

    notif.users.add(app.student.user)

    return redirect("staff_panel")


# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────

@login_required
def dashboard(request):
    return render(request, "od/dashboard.html")