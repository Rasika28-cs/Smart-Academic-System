from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.core.exceptions import PermissionDenied
from django.urls import reverse

from attendance.leave_app.utils import send_notification
from leave_app.models import ActivityLog, Notification, Student
from django.contrib.auth.models import User
from .models import ODApplication
from events.models import Event
from django.core.mail import send_mail
from django.db import transaction
# ─────────────────────────────────────────────
# OD STATUS
# ─────────────────────────────────────────────

@login_required
def view_od_status(request):
    ods = (
        ODApplication.objects.filter(student=request.user)
        .select_related("event")
        .order_by("-date")
    )

    return render(
        request,
        "od/od_status.html",
        {"ods": ods},
    )


# ─────────────────────────────────────────────
# APPLY OD
# ─────────────────────────────────────────────
@login_required
@require_POST
def apply_od(request, event_id):
    event = get_object_or_404(Event, id=event_id)

    # ── DUPLICATE GUARD ───────────────────────────────────────────────────────
    if ODApplication.objects.filter(
        student=request.user,
        event=event,
    ).exists():
        return redirect("event_list")

    # ── AUTO-APPROVE LOGIC ────────────────────────────────────────────────────
    approved_count = ODApplication.objects.filter(
        date=event.event_date,
        status="approved",
    ).count()
    status = "approved" if approved_count < 8 else "pending"

    # ── 1. SAVE (ATOMIC, ISOLATED) ────────────────────────────────────────────
    # Notification and email are intentionally outside — a failure there
    # must never roll back the OD record.
    with transaction.atomic():
        ODApplication.objects.create(
            student=request.user,
            event=event,
            date=event.event_date,
            status=status,
        )

    # ── 2. RECIPIENTS (QUERIED ONCE, REUSED BELOW) ───────────────────────────
    staff_users = User.objects.filter(is_staff=True, is_active=True)

    # ── 3. IN-APP NOTIFICATION ────────────────────────────────────────────────
    try:
        send_notification(
            title="New OD Request",
            message=(
                f"{request.user.username} applied for OD: {event.event_name}"
            ),
            notif_type="od",
            url=reverse("staff_panel"),
            users=staff_users,
        )
    except Exception as e:
        print(f"[apply_od] Notification error: {e}")

    # ── 4. EMAIL ──────────────────────────────────────────────────────────────
    try:
        staff_emails = list(
            staff_users.exclude(email="")
            .values_list("email", flat=True)
            .distinct()
        )
        if staff_emails:
            send_mail(
                subject="New OD Request - Smart Academic System",
                message=(
                    f"Student  : {request.user.username}\n"
                    f"Event    : {event.event_name}\n"
                    f"Date     : {event.event_date}\n"
                    f"Status   : {status.upper()}\n\n"
                    f"Please log in to review the request."
                ),
                from_email=None,
                recipient_list=staff_emails,
                fail_silently=False,  # real errors surface to the except log
            )
    except Exception as e:
        print(f"[apply_od] Email error: {e}")

    # ── 5. ACTIVITY LOG ───────────────────────────────────────────────────────
    try:
        ActivityLog.objects.create(
            user=request.user,
            action=f"Applied OD for event '{event.event_name}' on {event.event_date}",
            ip_address=request.META.get("REMOTE_ADDR", ""),
        )
    except Exception as e:
        print(f"[apply_od] ActivityLog error: {e}")

    return redirect("event_list")
# ─────────────────────────────────────────────
# STAFF PANEL
# ─────────────────────────────────────────────

@login_required
def staff_panel(request):
    if not request.user.is_staff:
        raise PermissionDenied("Only staff allowed")

    batch = request.GET.get("batch")

    applications = (
        ODApplication.objects.filter(status="pending")
        .select_related("student", "event")
        .order_by("-date")
    )

    if batch:
        applications = applications.filter(
            student__student_profile__batch=batch
        )

    batches = (
        Student.objects.values_list("batch", flat=True)
        .distinct()
        .order_by("batch")
    )

    return render(
        request,
        "od/staff.html",
        {
            "applications": applications,
            "batches": batches,
            "selected_batch": batch,
        },
    )


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
    app.save(update_fields=["status"])

    notif = Notification.objects.create(
        title="OD Approved",
        message=f"Your OD request for {app.event.event_name} has been approved.",
        type="od",
        url=reverse("od_status"),
    )

    notif.users.add(app.student)

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
    app.save(update_fields=["status"])

    notif = Notification.objects.create(
        title="OD Rejected",
        message=f"Your OD request for {app.event.event_name} has been rejected.",
        type="od",
        url=reverse("od_status"),
    )

    notif.users.add(app.student)

    return redirect("staff_panel")


# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────

@login_required
def dashboard(request):
    return render(request, "od/dashboard.html")