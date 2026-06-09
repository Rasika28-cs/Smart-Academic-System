import json
import io
import csv
import pandas as pd
import qrcode
from datetime import date, datetime, timedelta
from functools import wraps
from django.http import HttpResponse
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User, Group
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import Count, Q, Case, When, FloatField, F, ExpressionWrapper, Avg, Sum
from django.db.models.functions import Cast
from django.utils import timezone
from django.core.exceptions import PermissionDenied

# Models from your app
from .models import (
    Student, LeaveRequest, Attendance, Notification, DefaulterStudent,
    Department, Subject, Timetable, Assignment,
    ParentProfile,  ActivityLog
)
# Models from existing related apps
from department.models import Staff, Achievement, Winner, Gallery, NewsItem, UpcomingEvent
from od.models import ODApplication


from django.shortcuts import get_object_or_404, render
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.db import transaction
from django.contrib import messages
from .models import LeaveRequest
from .models import GradeUpload, StudentGrade
from .models import Notification

def process_leave_decision(request, leave_id, action):
    """
    Action can be 'APPROVED' or 'REJECTED'
    """
    # 1. Standard Role Check (Ensure user is authorized to act)
    # Logic to verify if user is the student's Mentor OR Class Incharge
    
    with transaction.atomic():
        # 2. SELECT ... FOR UPDATE (Locks this row in the DB)
        leave = LeaveRequest.objects.select_for_update().get(id=leave_id)

        # 3. LOCK RULE: Check if already processed
        if leave.status != 'PENDING':
            messages.error(request, f"Action denied. This request was already {leave.status} by {leave.decided_by}.")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

        # 4. FIRST ACTION WINS: Update fields
        leave.status = action # 'APPROVED' or 'REJECTED'
        leave.decided_by = request.user
        leave.decided_at = timezone.now()
        
        # Optional: Determine role of decider
        # leave.decided_by_role = "Mentor" if is_mentor else "Class Incharge"
        
        leave.save()
        messages.success(request, f"Leave {action.lower()} successfully.")

    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

# ─────────────────────────────────────────────
# 1. HELPERS & ROLE-BASED ACCESS CONTROL
# ─────────────────────────────────────────────

def role_required(*group_names):
    """
    Decorator for views that checks whether a user has a particular group role.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login_page')
            if request.user.is_superuser or request.user.groups.filter(name__in=group_names).exists():
                return view_func(request, *args, **kwargs)
            raise PermissionDenied
        return _wrapped_view
    return decorator

def is_class_incharge(user):
    return user.is_authenticated and (user.groups.filter(name='ClassIncharge').exists() or user.is_superuser)

def is_mentor(user):
    return user.is_authenticated and (user.groups.filter(name='Mentor').exists() or user.is_superuser)

def _get_student(request):
    """Return the Student linked to the logged-in Django user, or None."""
    try:
        return request.user.student_profile
    except (AttributeError, Student.DoesNotExist):
        return None

def _student_required(request):
    """
    Standard check to ensure the user is an authenticated student.
    """
    if not request.user.is_authenticated:
        return None, redirect('login_page')
    student = _get_student(request)
    if student is None:
        return None, redirect('login_page')
    return student, None


# ─────────────────────────────────────────────
# 2. HOME & LOGIN ROUTING (LEGACY PRESERVED)
# ─────────────────────────────────────────────

def home(request):
    if request.user.is_authenticated:
        if request.user.is_superuser:
            return redirect('hod_dashboard')
        elif is_class_incharge(request.user):
            return redirect('class_incharge_dashboard')
        elif is_mentor(request.user):
            return redirect('mentor_dashboard')
        elif request.user.is_staff:
            return redirect('teacher_dashboard')
        elif is_classrep(request.user):   # ✅ FIX HERE
            return redirect('cr_dashboard')

        student = _get_student(request)
        if student:
            return redirect('student_dashboard')

    context = {
        'staff': Staff.objects.all(),
        'achievements': Achievement.objects.all(),
        'winners': Winner.objects.all(),
        'gallery_images': Gallery.objects.all()[:12],
        'news_items': NewsItem.objects.filter(is_active=True)[:20],
        'upcoming_events': UpcomingEvent.objects.filter(is_active=True)[:20],
    }
    return render(request, 'index.html', context)


def login_page(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        next_url = request.POST.get('next') or request.GET.get('next')

        # Standard Django Auth
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            if next_url: return redirect(next_url)
            if user.is_superuser: return redirect('hod_dashboard')
            elif is_class_incharge(user): return redirect('class_incharge_dashboard')
            elif is_mentor(user): return redirect('mentor_dashboard')
            elif user.is_staff: return redirect('teacher_dashboard')
            elif is_classrep(user):return redirect('cr_dashboard')
            return redirect('student_dashboard')

        # Legacy Fallback Logic (Roll No based login)
        try:
            student_obj = Student.objects.get(roll_no=username)
            if student_obj.password and check_password(password, student_obj.password):
                django_user, created = User.objects.get_or_create(username=student_obj.roll_no)
                if created:
                    django_user.set_password(password)
                    django_user.first_name = student_obj.name
                    django_user.save()
                student_obj.user = django_user
                student_obj.save()
                login(request, django_user)
                if next_url: return redirect(next_url)
                return redirect('student_dashboard')
        except Student.DoesNotExist:
            pass

        return render(request, 'login.html', {'error': 'Invalid credentials'})

    return render(request, 'login.html')


def logout_view(request):
    logout(request)
    return redirect('login_page')


def signup_page(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        roll_no = request.POST.get('roll_no', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        if not name or not roll_no:
            return render(request, 'signup.html', {'error': 'Name and Roll No are required'})
        if password != confirm_password:
            return render(request, 'signup.html', {'error': 'Passwords do not match'})
        if Student.objects.filter(roll_no=roll_no).exists() or User.objects.filter(username=roll_no).exists():
            return render(request, 'signup.html', {'error': 'Roll number already registered'})
        
        django_user = User.objects.create_user(username=roll_no, password=password, first_name=name)
        Student.objects.create(user=django_user, name=name, roll_no=roll_no, password=make_password(password))
        return redirect('login_page')
    return render(request, 'signup.html')
from django.contrib.auth.hashers import check_password
from django.contrib.auth import login


def parent_login(request):
    if request.method == 'POST':

        reg_no = request.POST.get('reg_no')
        password = request.POST.get('password')

        try:
            student = Student.objects.get(reg_no=reg_no)

            # 🔥 YOUR RULE:
            # password must equal reg_no OR student's stored password
            if password == student.reg_no or check_password(password, student.password):

                user = student.user

                if not user:
                    user = User.objects.create_user(
                        username=student.reg_no,
                        password=student.reg_no,   # 🔥 password = reg_no
                        first_name=student.name
                    )
                    student.user = user
                    student.save()

                login(request, user)

                ParentProfile.objects.get_or_create(
                    user=user,
                    student=student
                )

                return redirect('parent_dashboard')

            return render(request, 'parent_login.html', {
                'error': 'Invalid credentials'
            })

        except Student.DoesNotExist:
            return render(request, 'parent_login.html', {
                'error': 'Student not found'
            })

    return render(request, 'parent_login.html')

# ─────────────────────────────────────────────
# 3. STUDENT MODULES
# ─────────────────────────────────────────────
@login_required
def dashboard(request):
    student, err = _student_required(request)
    if err:
        return err

    total_leaves = LeaveRequest.objects.filter(student=student).count()

    pending_leaves = LeaveRequest.objects.filter(
        student=student,
        status__icontains='PENDING'
    ).count()

    records = Attendance.objects.filter(student=student)

    p = records.filter(status='Present').count()
    l = records.filter(status='Leave').count()
    a = records.filter(status='Absent').count()

    total_classes = p + l + a

    # ─────────────────────────────
    # Attendance Logic (YOUR RULE)
    # ─────────────────────────────
    attendance_percent = 100 - ((l + a) * 3)

    if attendance_percent < 0:
        attendance_percent = 0

    context = {
        'student': student,
        'total_leaves': total_leaves,
        'pending_leaves': pending_leaves,
        'attendance_percent': round(attendance_percent, 2),
        'present_classes': p,
        'total_classes': total_classes,
        'upcoming_assignments': Assignment.objects.filter(
            batch=student.batch,
            due_date__gte=timezone.now()
        ),
        'today_timetable': Timetable.objects.filter(
            batch=student.batch,
            day=date.today().strftime('%a')
        )
    }

    return render(request, 'dashboard.html', context)


@login_required
def attendance(request):
    student, err = _student_required(request)
    if err: return err
    records = Attendance.objects.filter(student=student).order_by('-date')
    return render(request, 'attendance.html', {'attendance': records})



def _student_required(request):
    try:
        student = Student.objects.get(user=request.user)
        return student, None
    except Student.DoesNotExist:
        return None, HttpResponse('Unauthorized', status=403)


def _redirect_after_review(user, leave=None):
    if user.is_superuser:
        return redirect('teacher_dashboard')

    if hasattr(leave, "student"):
        if leave.student.class_incharge == user:
            return redirect('class_incharge_dashboard')
        if leave.student.mentor == user:
            return redirect('mentor_dashboard')

    if user.groups.filter(name='Mentor').exists():
        return redirect('mentor_dashboard')

    if user.groups.filter(name='ClassIncharge').exists():
        return redirect('class_incharge_dashboard')

    return redirect('teacher_dashboard')


# ─────────────────────────────
# STUDENT VIEWS
# ─────────────────────────────

def is_student_on_leave(student, check_date):
    """
    Returns True if an approved leave request covers the check_date for a student.
    """
    return LeaveRequest.objects.filter(
        student=student,
        from_date__lte=check_date,
        to_date__gte=check_date,
        status='APPROVED'
    ).exists()


@login_required
def view_students(request):
    if not request.user.is_staff:
        return redirect('home')

    students = Student.objects.all().order_by('roll_no')
    return render(request, 'view_students.html', {'students': students})


@login_required
def leave_status(request):
    student, err = _student_required(request)
    if err: 
        return err

    leaves = LeaveRequest.objects.filter(student=student).order_by('-created_at')
    return render(request, 'leave_status.html', {'leaves': leaves})


@login_required
def apply_page(request):
    student, err = _student_required(request)
    if err: 
        return err

    return render(request, 'apply.html')


@login_required
def student_defaulter_view(request):
    student, err = _student_required(request)
    if err: 
        return err

    defaulters = DefaulterStudent.objects.filter(
        roll_no=student.roll_no
    ).order_by('year')

    return render(request, 'student_defaulter.html', {'students': defaulters})


# ─────────────────────────────
# LEAVE APPLICATION API
# ─────────────────────────────
@login_required
def apply_leave_api(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error'})

    student, err = _student_required(request)
    if err:
        return JsonResponse({'status': 'error', 'message': 'Not a student'})

    try:
        data = json.loads(request.body)

        from_date = datetime.strptime(data['from_date'], "%Y-%m-%d").date()
        to_date = datetime.strptime(data['to_date'], "%Y-%m-%d").date()

        if from_date < date.today():
            return JsonResponse({'status': 'error', 'message': 'Past date not allowed'})
        if from_date > to_date:
            return JsonResponse({'status': 'error', 'message': 'Invalid range'})

        overlap = LeaveRequest.objects.filter(
            student=student,
            from_date__lte=to_date,
            to_date__gte=from_date
        ).exclude(status='REJECTED')

        if overlap.exists():
            return JsonResponse({'status': 'error', 'message': 'Already applied'})

        LeaveRequest.objects.create(
            student=student,
            from_date=from_date,
            to_date=to_date,
            reason=data.get('reason'),
            status='PENDING'
        )

        # NEW NOTIFICATION
        notif = Notification.objects.create(
            title="New Leave Request",
            message=f"{student.name} submitted a leave request from {from_date} to {to_date}.",
            type="leave",
            url=reverse('today_leaves')
        )

        if student.mentor:
            notif.users.add(student.mentor)

        if student.class_incharge:
            notif.users.add(student.class_incharge)

        ActivityLog.objects.create(
            user=request.user,
            action=f"Applied leave {from_date}-{to_date}",
            ip_address=request.META.get('REMOTE_ADDR')
        )

        return JsonResponse({'status': 'success'})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})


# ─────────────────────────────
# DASHBOARDS
# ─────────────────────────────
@login_required
def mentor_dashboard(request):
    if not request.user.groups.filter(name='Mentor').exists():
        return redirect('home')

    leaves = LeaveRequest.objects.filter(status='PENDING')
    if not request.user.is_superuser:
        leaves = leaves.filter(student__mentor=request.user)

    return render(request, 'mentor_dashboard.html', {
        'leaves': leaves,
        'pending_leaves_count': leaves.count(),
        'pending_od': ODApplication.objects.filter(status='pending').count()
    })


@login_required
def class_incharge_dashboard(request):
    if not request.user.groups.filter(name='ClassIncharge').exists():
        return redirect('home')

    leaves = LeaveRequest.objects.filter(status='APPROVED_BY_MENTOR')
    if not request.user.is_superuser:
        leaves = leaves.filter(student__class_incharge=request.user)

    return render(request, 'class_incharge_dashboard.html', {
        'leaves': leaves,
        'pending_leaves_count': leaves.count(),
        'pending_od': ODApplication.objects.filter(status='pending').count()
    })


@login_required
def teacher_dashboard(request):
    if not request.user.is_staff:
        return redirect('home')

    context = {
        'pending_leaves': LeaveRequest.objects.filter(status__icontains='PENDING').count(),
        'pending_od': ODApplication.objects.filter(status='pending').count()
    }

    # CI users
    if request.user.groups.filter(name='CI').exists():
        return render(request, 'ci_dashboard.html', context)

    # Mentor users
    elif request.user.groups.filter(name='MENTOR').exists():
        return render(request, 'mentor_dashboard.html', context)

    # Fallback
    return redirect('home')

# ─────────────────────────────
# HIERARCHICAL APPROVAL ENGINE
# ─────────────────────────────

@login_required
def review_leave(request, leave_id, action):
    if action not in ['approve', 'reject']:
        raise PermissionDenied()

    user = request.user

    try:
        with transaction.atomic():

            leave = LeaveRequest.objects.select_related(
                'student',
                'student__user',
                'student__mentor',
                'student__class_incharge'
            ).select_for_update().get(id=leave_id)

            is_mentor = leave.student.mentor == user
            is_ci = leave.student.class_incharge == user

            if not (is_mentor or is_ci or user.is_superuser):
                raise PermissionDenied()

            # Only pending leaves can be reviewed
            if leave.status != 'PENDING':
                return _redirect_after_review(user, leave)

            if action == 'approve':

                leave.status = 'APPROVED'
                msg = "Leave approved"

                # Auto-create attendance records
                curr = leave.from_date

                while curr <= leave.to_date:

                    timetable = Timetable.objects.filter(
                        batch=leave.student.batch,
                        department=leave.student.department,
                        day=curr.strftime('%a')
                    ).select_related('subject')

                    if timetable.exists():

                        for slot in timetable:

                            attendance, created = Attendance.objects.get_or_create(
                                student=leave.student,
                                subject=slot.subject,
                                date=curr,
                                defaults={'status': 'Leave'}
                            )

                            if not created and attendance.status != 'Leave':
                                attendance.status = 'Leave'
                                attendance.save(update_fields=['status'])

                    else:
                        attendance, created = Attendance.objects.get_or_create(
                            student=leave.student,
                            subject=None,
                            date=curr,
                            defaults={'status': 'Leave'}
                        )

                        if not created and attendance.status != 'Leave':
                            attendance.status = 'Leave'
                            attendance.save(update_fields=['status'])

                    curr += timedelta(days=1)

            else:
                leave.status = 'REJECTED'
                msg = "Leave rejected"

            leave.reviewed_by = user

            if user.is_superuser:
                leave.reviewer_role = 'Superuser'
            elif is_ci:
                leave.reviewer_role = 'Class Incharge'
            else:
                leave.reviewer_role = 'Mentor'

            leave.reviewed_at = timezone.now()
            leave.save()

            notification = Notification.objects.create(
                title="Leave Update",
                message=msg,
                type="leave",
                url=reverse('leave_status')
            )
            notification.users.add(leave.student.user)

            ActivityLog.objects.create(
                user=user,
                action=f"{action.upper()} leave {leave.id}",
                ip_address=request.META.get('REMOTE_ADDR')
            )

    except LeaveRequest.DoesNotExist:
        raise Http404()

    return _redirect_after_review(user, leave)

@login_required
def mark_attendance(request):
    if not request.user.is_staff:
        return HttpResponse('Unauthorized', status=403)

    today = date.today()
    students = Student.objects.all().order_by('roll_no')

    # Students having approved leave today
    students_on_leave_ids = set(
        LeaveRequest.objects.filter(
            from_date__lte=today,
            to_date__gte=today,
            status='APPROVED'
        ).values_list('student_id', flat=True)
    )

    # Existing attendance records for today
    attendance_records = Attendance.objects.filter(
        date=today
    ).select_related('student')

    attendance_map = {}
    for att in attendance_records:
        if att.student_id not in attendance_map:
            attendance_map[att.student_id] = att.status

    if request.method == 'POST':
        for student in students:
            # Skip students on approved leave
            if student.id in students_on_leave_ids:
                continue

            status = request.POST.get(f'status_{student.id}')
            if not status:
                continue

            # Update existing attendance records of the student for today
            updated_count = Attendance.objects.filter(
                student=student,
                date=today
            ).update(status=status)

            # If no attendance entries existed yet, generate them dynamically
            if updated_count == 0:
                day = today.strftime('%a')
                timetable = Timetable.objects.filter(
                    batch=student.batch,
                    department=student.department,
                    day=day
                )

                if timetable.exists():
                    for t in timetable:
                        Attendance.objects.get_or_create(
                            student=student,
                            subject=t.subject,
                            date=today,
                            defaults={'status': status}
                        )
                else:
                    Attendance.objects.get_or_create(
                        student=student,
                        subject=None,
                        date=today,
                        defaults={'status': status}
                    )

        messages.success(request, "Attendance marked successfully")
        return redirect('teacher_dashboard')

    student_data = []
    for student in students:
        is_on_leave = student.id in students_on_leave_ids

        if is_on_leave:
            current_status = 'Leave'
        else:
            current_status = attendance_map.get(student.id, 'Present')

        student_data.append({
            'student': student,
            'status': current_status,
            'is_on_leave': is_on_leave
        })

    return render(
        request,
        'mark_attendance.html',
        {
            'student_data': student_data,
            'today': today
        }
    )
# ─────────────────────────────
# TODAY LEAVES
# ─────────────────────────────
@login_required
def today_leaves(request):
    if not request.user.is_staff:
        return redirect('home')

    today = date.today()
    batch = request.GET.get('batch')

    leaves = LeaveRequest.objects.filter(
        from_date__lte=today,
        to_date__gte=today,
        status__in=['PENDING', 'APPROVED']
    ).select_related('student')

    if batch:
        leaves = leaves.filter(student__batch=batch)

    return render(request, 'today_leaves.html', {
        'leaves': leaves,
        'batches': Student.objects.values_list('batch', flat=True).distinct(),
        'selected_batch': batch
    })
# ─────────────────────────────────────────────
# 6. HOD DASHBOARD & ANALYTICS (OPTIMIZED)
# ─────────────────────────────────────────────

@login_required
@role_required('HOD')
def hod_dashboard(request):

    search_query = request.GET.get('search', '')
    sort_order = request.GET.get('sort', '')
    selected_date = request.GET.get('date')

    # ─────────────────────────────────────────────
    # STEP 1: Get HOD Department
    # ─────────────────────────────────────────────
    try:
        managed_dept = request.user.managed_dept.first()
        
    except Exception:
        return HttpResponse("You are not assigned to any department.")

    if not managed_dept:
        return HttpResponse("You are not assigned to any department.")

    # ─────────────────────────────────────────────
    # STEP 2: Department-Filtered Students
    # ─────────────────────────────────────────────
    students = Student.objects.filter(
    department=managed_dept
).annotate(
    total=Count('attendance'),
    p=Count('attendance', filter=Q(attendance__status='Present')),
    l=Count('attendance', filter=Q(attendance__status='Leave')),
    a=Count('attendance', filter=Q(attendance__status='Absent')),
).annotate(
    perc=Case(
        When(
            total__gt=0,
            then=100 - ((F('l') + F('a')) * 3)
        ),
        default=0.0,
        output_field=FloatField()
    )
).order_by('-perc')

    # ─────────────────────────────────────────────
    # STEP 3: Search Filter
    # ─────────────────────────────────────────────
    if search_query:
        students = students.filter(
            Q(name__icontains=search_query) |
            Q(roll_no__icontains=search_query)
        )

    # ─────────────────────────────────────────────
    # STEP 4: Sorting
    # ─────────────────────────────────────────────
    if sort_order == 'low':
        students = students.order_by('perc')

    # ─────────────────────────────────────────────
    # STEP 5: Trend Analytics (Last 21 Days)
    # ─────────────────────────────────────────────
    today_dt = date.today()
    start_date = today_dt - timedelta(days=21)

    trend_data = Attendance.objects.filter(
        student__department=managed_dept,
        date__gte=start_date
    ).values('date').annotate(
        present_count=Count('id', filter=Q(status='Present'))
    ).order_by('date')

    trend_labels = [d['date'].strftime('%b %d') for d in trend_data]
    trend_values = [d['present_count'] for d in trend_data]

    # ─────────────────────────────────────────────
    # STEP 6: Subject-wise Attendance (Department Only)
    # ─────────────────────────────────────────────
    subject_stats = Attendance.objects.filter(
        student__department=managed_dept
    ).values(
        'subject__name',
        'subject__code'
    ).annotate(
        total=Count('id'),
        present=Count('id', filter=Q(status='Present')),
        leave=Count('id', filter=Q(status='Leave')),
    ).annotate(
        perc=Case(
            When(
                total__gt=0,
                then=(F('present') * 100.0) / F('total')
            ),
            default=0.0,
            output_field=FloatField()
        )
    ).order_by('subject__name')

    sub_names = [s['subject__name'] or 'General' for s in subject_stats]
    sub_percs = [round(s['perc'], 2) for s in subject_stats]

    # ─────────────────────────────────────────────
    # STEP 7: Overall Attendance Distribution
    # ─────────────────────────────────────────────
    total_stats = Attendance.objects.filter(
        student__department=managed_dept
    ).aggregate(
        p=Count('id', filter=Q(status='Present')),
        l=Count('id', filter=Q(status='Leave')),
        a=Count('id', filter=Q(status='Absent'))
    )

    dist_data = [
        total_stats['p'] or 0,
        total_stats['l'] or 0,
        total_stats['a'] or 0
    ]

    # ─────────────────────────────────────────────
    # STEP 8: Summary Stats
    # ─────────────────────────────────────────────
    total_students = Student.objects.filter(department=managed_dept).count()

    above_75_count = students.filter(perc__gte=75).count()
    below_75_count = students.filter(perc__lt=75).count()

    dept_avg = students.aggregate(avg=Avg('perc'))['avg'] or 0

    # ─────────────────────────────────────────────
    # STEP 9: Top 12 Students for Chart
    # ─────────────────────────────────────────────
    names = [s.name for s in students[:12]]
    percentages = [round(s.perc, 2) for s in students[:12]]

    # ─────────────────────────────────────────────
    # STEP 10: Daily Records Filter
    # ─────────────────────────────────────────────
    daily_records = []
    if selected_date:
        daily_records = Attendance.objects.filter(
            student__department=managed_dept,
            date=selected_date
        ).select_related('student')

    # ─────────────────────────────────────────────
    # FINAL RENDER
    # ─────────────────────────────────────────────
    # Defaulters (from DefaulterStudent model)
    dept_code = managed_dept.code.strip()

    defaulter_list = DefaulterStudent.objects.filter(
        department__icontains=dept_code
    ).order_by('year', 'roll_no')

    # Grade Uploads for this department's students
    grade_uploads = GradeUpload.objects.all().order_by('-id')[:5]

    # Recent grades
    recent_grades = StudentGrade.objects.filter(
        student__department=managed_dept
    ).select_related('student', 'upload').order_by('-id')[:50]
    
        
    
    return render(request, 'hod_dashboard.html', {
    'students': students,
    'managed_dept': managed_dept,

    'names': json.dumps(names),
    'percentages': json.dumps(percentages),
    'trend_labels': json.dumps(trend_labels),
    'trend_values': json.dumps(trend_values),
    'sub_names': json.dumps(sub_names),
    'sub_percs': json.dumps(sub_percs),
    'dist_data': json.dumps(dist_data),

    'total_students': total_students,
    'above_75_count': above_75_count,
    'below_75_count': below_75_count,
    'department_average': round(dept_avg, 1),

    'search_query': search_query,
    'selected_date': selected_date,
    'daily_records': daily_records,

    'defaulter_list': defaulter_list,
    'grade_uploads': grade_uploads,
    'recent_grades': recent_grades,
})


from reportlab.platypus import SimpleDocTemplate, Table
from django.http import HttpResponse

@login_required
@role_required('HOD')
def attendance_report_pdf(request):

    managed_dept = request.user.managed_dept.first()

    students = Student.objects.filter(department=managed_dept)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="attendance_report.pdf"'

    doc = SimpleDocTemplate(response)

    data = [[
        'Roll No',
        'Name',
        'Department'
    ]]

    for s in students:
        data.append([
            s.roll_no,
            s.name,
            managed_dept.code
        ])

    table = Table(data)

    doc.build([table])

    return response


from reportlab.platypus import SimpleDocTemplate, Table
from django.http import HttpResponse

@login_required
@role_required('HOD')
def defaulter_report_pdf(request):

    managed_dept = request.user.managed_dept.first()

    defaulters = DefaulterStudent.objects.filter(
        department__icontains=managed_dept.code
    )

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="defaulter_report.pdf"'

    doc = SimpleDocTemplate(response)

    data = [[
        'Roll No',
        'Name',
        'Year',
        'Reason',
        'Staff Incharge',
        'Action'
    ]]

    for d in defaulters:
        data.append([
            d.roll_no,
            d.name,
            str(d.year),
            d.reason,
            d.staff_incharge,
            d.action_taken or '-'
        ])

    table = Table(data)

    doc.build([table])

    return response
# ─────────────────────────────────────────────
# 7. UTILS: QR, CALCULATOR, CSV UPLOADS
# ─────────────────────────────────────────────

def calculator(request):
    return render(request, 'calculator.html')


def generate_qr(request):
    url = request.build_absolute_uri(reverse('home'))
    img = qrcode.make(url)
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return HttpResponse(buffer.getvalue(), content_type='image/png')


@login_required
def upload_attendance(request):
    if request.method == 'POST':
        file = request.FILES.get('file')
        if not file:
            messages.error(request, 'No file uploaded')
        else:
            try:
                decoded = file.read().decode('utf-8').splitlines()
                reader = csv.DictReader(decoded)
                count = 0
                for row in reader:
                    roll_no = row.get('student_roll')
                    r_date = row.get('date')
                    status = row.get('status')
                    try:
                        std = Student.objects.get(roll_no=roll_no)
                        Attendance.objects.update_or_create(student=std, date=r_date, defaults={'status': status})
                        count += 1
                    except Student.DoesNotExist: continue
                messages.success(request, f'{count} records processed.')
            except Exception as e:
                messages.error(request, f'Error: {str(e)}')
    return render(request, 'upload.html')


# ─────────────────────────────────────────────
# 8. NOTIFICATIONS & DEFAULTERS (LEGACY)
# ─────────────────────────────────────────────

@login_required
def get_notifications(request):
    notifications = Notification.objects.filter(users=request.user).order_by('-created_at')
    unread = notifications.exclude(read_by=request.user)
    data = {
        "total": unread.count(),
        "notifications": [{
            "id": n.id, "title": n.title, "message": n.message, 
            "time": n.created_at.strftime("%d %b %I:%M %p"), 
            "url": n.url, "read": request.user in n.read_by.all()
        } for n in notifications[:10]]
    }
    return JsonResponse(data)


@require_POST
@login_required
def mark_as_read(request, id):
    notif = get_object_or_404(Notification, id=id)
    notif.read_by.add(request.user)
    return JsonResponse({"status": "ok"})


@login_required
def upload_defaulters(request):
    if request.method != 'POST':
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid request'
        })

    file = request.FILES.get('excel_file')

    if not file:
        return JsonResponse({
            'status': 'error',
            'message': 'No file uploaded'
        })

    try:
        df = pd.read_excel(file)
        df.columns = df.columns.str.strip()

        required_cols = [
            'Roll No',
            'Name',
            'Staff Incharge',
            'Dept',
            'Year',
            'Reason'
        ]

        if not all(col in df.columns for col in required_cols):
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid Excel format'
            })

        # Clean department values
        df['Dept'] = (
            df['Dept']
            .fillna('')
            .astype(str)
            .str.strip()
            .str.upper()
        )

        print("Departments found:", df['Dept'].unique())

        # Match CYSE, CYSE (CS), cyse, etc.
        df = df[df['Dept'].str.contains('CYSE', na=False)]

        print("Rows after filter:", len(df))

        uploaded_count = 0

        for _, row in df.iterrows():

            roll_no_str = str(row['Roll No']).strip()
            reason_str = str(row['Reason']).strip()

            existing_defaulter = DefaulterStudent.objects.filter(
                roll_no=roll_no_str
            ).first()

            should_notify = False

            if not existing_defaulter:
                should_notify = True

            elif existing_defaulter.reason != reason_str:
                should_notify = True

            DefaulterStudent.objects.update_or_create(
                roll_no=roll_no_str,
                defaults={
                    'name': str(row['Name']).strip(),
                    'staff_incharge': str(row['Staff Incharge']).strip(),
                    'department': str(row['Dept']).strip(),
                    'year': int(row['Year']),
                    'reason': reason_str
                }
            )

            if should_notify:
                try:
                    student_obj = Student.objects.get(
                        roll_no=roll_no_str
                    )

                    notif = Notification.objects.create(
                        title="Defaulter Alert",
                        message=f"You have been marked as a defaulter. Reason: {reason_str}",
                        type="defaulter",
                        url=reverse('student_defaulter')
                    )

                    notif.users.add(student_obj.user)

                except Student.DoesNotExist:
                    pass

            uploaded_count += 1

        return JsonResponse({
            'status': 'success',
            'message': f'{uploaded_count} records uploaded'
        })

    except Exception as e:
        print("Upload Error:", str(e))
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        })
    

def defaulter_list(request):
    students = DefaulterStudent.objects.all().order_by('year', 'roll_no')
    return render(request, 'defaulter_list.html', {'students': students})



@login_required
def update_action(request, id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request'})

    try:
        data = json.loads(request.body)

        student = DefaulterStudent.objects.get(id=id)
        student.action_taken = data.get('action')
        student.save()

        return JsonResponse({'status': 'success'})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})
# ─────────────────────────────────────────────
# 9. NEW ACADEMIC MODULES
# ─────────────────────────────────────────────
@login_required
def view_timetable(request):
    student = _get_student(request)

    if student:
        timetable = Timetable.objects.select_related(
            'department',
            'subject',
            'teacher'
        ).filter(
            batch=student.batch
        ).order_by('day', 'start_time')
    else:
        timetable = Timetable.objects.none()

    return render(request, 'timetable.html', {
        'timetable': timetable
    })


@login_required
def assignment_list(request):
    student, err = _student_required(request)
    if err: return err
    data = Assignment.objects.filter(batch=student.batch,due_date__gte=timezone.now().date() ).order_by('-due_date')
    return render(request, 'assignments.html', {'assignments': data})

@login_required
@role_required('ClassRep')
def manage_assignments(request):
    student = request.user.student_profile

    assignments = Assignment.objects.filter(
        batch=student.batch
    ).order_by('-created_at')

    return render(request, 'manage_assignments.html', {
        'assignments': assignments
    })

@login_required
@role_required('ClassRep')
def edit_assignment(request, assignment_id):

    student = request.user.student_profile

    assignment = get_object_or_404(
        Assignment,
        id=assignment_id,
        batch=student.batch
    )

    if request.method == 'POST':

        assignment.title = request.POST.get('title')
        assignment.description = request.POST.get('description')
        assignment.subject_id = request.POST.get('subject')
        assignment.due_date = request.POST.get('due_date')

        if request.FILES.get('file'):
            assignment.file = request.FILES.get('file')

        assignment.save()

        messages.success(request, "Assignment updated successfully.")
        return redirect('manage_assignments')

    subjects = Subject.objects.all()

    return render(
        request,
        'create_assignment.html',
        {
            'assignment': assignment,
            'subjects': Subject.objects.all(),
            'batch': student.batch,
            'page_title': 'Edit Assignment',
            'button_text': 'Update Assignment'
        }
    )

@login_required
@role_required('ClassRep')
def delete_assignment(request, assignment_id):

    student = request.user.student_profile

    assignment = get_object_or_404(
        Assignment,
        id=assignment_id,
        batch=student.batch
    )

    assignment.delete()

    messages.success(request, "Assignment deleted successfully.")
    return redirect('manage_assignments')

# OD Integration
@login_required
def view_od_status(request):
    ods = ODApplication.objects.filter(student=request.user)
    return render(request, 'od_status.html', {'ods': ods})

@login_required
def dashboard_redirect(request):
    user = request.user

    if user.is_superuser:
        return redirect('hod_dashboard')

    elif user.groups.filter(name='ClassIncharge').exists():
        return redirect('class_incharge_dashboard')

    elif user.groups.filter(name='Mentor').exists():
        return redirect('mentor_dashboard')

    elif user.is_staff:
        return redirect('teacher_dashboard')

    elif user.groups.filter(name='ClassRep').exists():
        return redirect('cr_dashboard')

    elif hasattr(user, 'parentprofile'):
        return redirect('parent_dashboard')

    elif hasattr(user, 'student_profile'):
        return redirect('student_dashboard')

    return redirect('login_page')


from django.db.models import Count

@login_required
def parent_dashboard(request):
    try:
        parent = request.user.parent_profile
        student = parent.student
    except ParentProfile.DoesNotExist:
        return redirect('login_page')

    # ─────────────────────────
    # Attendance (optimized)
    # ─────────────────────────
    attendance_qs = Attendance.objects.filter(student=student)

    attendance_records = attendance_qs.order_by('-date')[:10]

    total = attendance_qs.count()
    present = attendance_qs.filter(status='Present').count()
    leave = attendance_qs.filter(status='Leave').count()
    absent = attendance_qs.filter(status='Absent').count()

    attendance_percent = max(0, 100 - ((leave + absent) * 3))

    # ─────────────────────────
    # Leaves
    # ─────────────────────────
    leaves = LeaveRequest.objects.filter(student=student).order_by('-created_at')[:5]

    # ─────────────────────────
    # OD
    # ─────────────────────────
    ods = ODApplication.objects.filter(student=student.user).order_by('-id')[:5]

    # ─────────────────────────
    # Grades
    # ─────────────────────────
    grades = StudentGrade.objects.filter(student=student).select_related('upload').order_by('-id')[:10]

    # ─────────────────────────
    # Defaulters
    # ─────────────────────────
    defaulters = DefaulterStudent.objects.filter(
        roll_no=student.roll_no
    ).order_by('-year')[:5]

    # ─────────────────────────
    # Notifications (IMPORTANT FIX)
    # ─────────────────────────
    notifications = Notification.objects.filter(
        users=student.user
    ).exclude(
        type__in=['assignment']
    ).order_by('-created_at')[:10]

    return render(request, 'parent_dashboard.html', {
        'student': student,

        # Attendance
        'attendance_records': attendance_records,
        'attendance_percent': round(attendance_percent, 2),
        'present': present,
        'leave': leave,
        'absent': absent,
        'total': total,

        # Modules
        'leaves': leaves,
        'ods': ods,
        'grades': grades,
        'defaulters': defaulters,
        'notifications': notifications,
    })


@login_required
def parent_view_attendance(request):
    parent = request.user.parent_profile
    student = parent.student

    records = Attendance.objects.filter(student=student).order_by('-date')

    return render(request, 'parent_attendance.html', {
        'attendance': records,
        'student': student
    })

@login_required
def parent_view_grades(request):
    parent = request.user.parent_profile
    student = parent.student

    grades = StudentGrade.objects.filter(student=student).select_related('upload')

    return render(request, 'parent_grades.html', {
        'grades': grades,
        'student': student
    })



@login_required
def parent_view_leaves(request):
    parent = request.user.parent_profile
    student = parent.student

    leaves = LeaveRequest.objects.filter(student=student).order_by('-created_at')

    return render(request, 'parent_leaves.html', {
        'leaves': leaves,
        'student': student
    })

@login_required
def parent_view_defaulters(request):
    parent = request.user.parent_profile
    student = parent.student

    defaulters = DefaulterStudent.objects.filter(roll_no=student.roll_no)

    return render(request, 'parent_defaulters.html', {
        'defaulters': defaulters,
        'student': student
    })

@login_required
def parent_view_od(request):
    parent = request.user.parent_profile
    student = parent.student

    ods = ODApplication.objects.filter(student=student.user)

    return render(request, 'parent_od.html', {
        'ods': ods,
        'student': student
    })

# ─────────────────────────────────────────────
# 1. ASSIGNMENT SUBMISSION SYSTEM #############
# ─────────────────────────────────────────────





@login_required
def parent_view_notifications(request):
    parent = get_object_or_404(ParentProfile, user=request.user)
    # Parents see notifications sent to their child's user account
    notifications = Notification.objects.filter(
        users=parent.student.user
    ).exclude(
        type__in=['assignment']
    ).order_by('-created_at')    
    return render(request, 'parent_notifications.html', {'notifications': notifications})

# ─────────────────────────────────────────────
# 3. SEMESTER & PROMOTION SYSTEM ##############
# ─────────────────────────────────────────────



# ─────────────────────────────────────────────
# 4. TEACHER SUBJECT MAPPING SYSTEM
# ─────────────────────────────────────────────

@login_required
@role_required('ClassRep')
def assign_teacher_subject(request):
    # In this schema, Timetable entries define which teacher handles which subject for a batch
    if request.method == 'POST':
        dept_id = request.POST.get('department')
        subject_id = request.POST.get('subject')
        teacher_id = request.POST.get('teacher')
        batch = request.POST.get('batch')
        
        # Logic to create or update mapping via Timetable or a custom Mapping model
        # Here we assume Timetable is the primary source of truth
        messages.success(request, "Teacher assigned to subject successfully.")
        return redirect('view_teacher_subjects')

    subjects = Subject.objects.all()
    teachers = User.objects.filter(is_staff=True)
    departments = Department.objects.all()
    return render(request, 'assign_subject.html', {
        'subjects': subjects, 'teachers': teachers, 'departments': departments
    })

@login_required
def view_teacher_subjects(request):
    # Teachers see subjects they are assigned to in the timetable
    mappings = Timetable.objects.filter(teacher=request.user).values(
        'subject__name', 'subject__code', 'batch', 'department__name'
    ).distinct()
    return render(request, 'teacher_subjects.html', {'mappings': mappings})

@login_required
def get_subject_students(request, subject_code, batch):
    if not request.user.is_staff:
        raise PermissionDenied
    students = Student.objects.filter(batch=batch).order_by('roll_no')
    return render(request, 'subject_students.html', {'students': students, 'subject_code': subject_code})

# ─────────────────────────────────────────────
# 5. CIRCULAR DISTRIBUTION SYSTEM ################
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
# 6. NOTIFICATION ENHANCEMENTS
# ─────────────────────────────────────────────

@login_required
def mark_all_notifications_read(request):
    notifications = Notification.objects.filter(users=request.user).exclude(read_by=request.user)
    for n in notifications:
        n.read_by.add(request.user)
    return JsonResponse({"status": "success"})

@login_required
def delete_notification(request, id):
    notification = get_object_or_404(Notification, id=id)
    if request.user in notification.users.all():
        notification.users.remove(request.user)
        return JsonResponse({"status": "success"})
    return JsonResponse({"status": "unauthorized"}, status=403)

# ─────────────────────────────────────────────
# 7. AUDIT LOG VIEWER
# ─────────────────────────────────────────────

@login_required
@role_required('HOD')
def view_activity_logs(request):
    user_filter = request.GET.get('user_id')
    date_filter = request.GET.get('date')
    
    logs = ActivityLog.objects.all().select_related('user').order_by('-timestamp')
    
    if user_filter:
        logs = logs.filter(user_id=user_filter)
    if date_filter:
        logs = logs.filter(timestamp__date=date_filter)
        
    return render(request, 'activity_logs.html', {'logs': logs})

# ─────────────────────────────────────────────
# 8. TIMETABLE CONFLICT PROTECTION VIEW
# ─────────────────────────────────────────────
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from .models import Timetable, Department, Subject
from django.contrib.auth.models import User


@login_required
@role_required('ClassRep')
def create_timetable_entry(request):

    if request.method == 'POST':

        day = request.POST.get('day')
        room = request.POST.get('room', '').strip()
        start = request.POST.get('start_time')
        end = request.POST.get('end_time')
        teacher_id = request.POST.get('teacher')
        subject_id = request.POST.get('subject')
        batch = request.POST.get('batch', '').strip()
        dept_id = request.POST.get('department')

        # Validation
        if not all([day, room, start, end, teacher_id, subject_id, batch, dept_id]):
            messages.error(request, "All fields are required.")
            return redirect('create_timetable_entry')

        # Teacher Clash Check
        teacher_clash = Timetable.objects.filter(
            day=day,
            teacher_id=teacher_id,
            start_time__lt=end,
            end_time__gt=start
        ).exists()

        # Room Clash Check
        room_clash = Timetable.objects.filter(
            day=day,
            room=room,
            start_time__lt=end,
            end_time__gt=start
        ).exists()

        if teacher_clash:
            messages.error(
                request,
                "Teacher is already assigned to another class during this time."
            )

        elif room_clash:
            messages.error(
                request,
                "Room is already occupied during this time."
            )

        else:
            department = Department.objects.get(id=dept_id)

            Timetable.objects.create(
                department=department,
                batch=batch,
                subject_id=subject_id,
                teacher_id=teacher_id,
                day=day,
                start_time=start,
                end_time=end,
                room=room
            )

            messages.success(request, "Timetable entry created successfully.")

        return redirect('view_timetable')

    # GET Request
    departments = Department.objects.all()
    subjects = Subject.objects.all()

    # If you don't have a Teacher model/role system
    teachers = User.objects.all()

    return render(request, 'create_timetable.html', {
        'departments': departments,
        'subjects': subjects,
        'teachers': teachers,
    })
import pandas as pd
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import GradeUpload, Student, StudentGrade


@login_required
def upload_grades(request):
    if request.method == 'POST':
        file = request.FILES.get('file')
        title = request.POST.get('title')
        semester = request.POST.get('semester')

        if not file:
            return render(request, 'upload_grades.html', {'error': 'Please upload a file'})

        upload = GradeUpload.objects.create(
            title=title,
            semester=semester,
            uploaded_file=file,
            uploaded_by=request.user
        )

        # READ FILE
        if file.name.endswith('.csv'):
            df = pd.read_csv(file, encoding='utf-8-sig')  # FIX BOM issue

        elif file.name.endswith('.xlsx'):
            df = pd.read_excel(file, engine='openpyxl')

        else:
            return render(request, 'upload_grades.html', {
                'error': 'Only CSV or XLSX files allowed'
            })

        # CLEAN COLUMN NAMES (VERY IMPORTANT)
        df.columns = df.columns.str.strip()

        print("COLUMNS FOUND:", df.columns.tolist())  # DEBUG

        # FIND register column safely
        reg_col = None
        for c in df.columns:
            if "register" in c.lower():
                reg_col = c
                break

        if not reg_col:
            return render(request, 'upload_grades.html', {
                'error': 'Register No column not found in file'
            })

        subject_columns = [c for c in df.columns if c != reg_col and c != "Student Name"]

        notified_student_ids = set()

        for _, row in df.iterrows():
            reg_no = str(row[reg_col]).strip()

            try:
                student = Student.objects.get(reg_no__iexact=reg_no)

                for subject_code in subject_columns:
                    grade = str(row[subject_code]).strip()

                    if grade and grade.lower() != "nan":
                        StudentGrade.objects.update_or_create(
                            upload=upload,
                            student=student,
                            subject_code=subject_code,
                            defaults={'grade': grade}
                        )

                # Send only one notification per student
                if student.id not in notified_student_ids and student.user:

                    notif = Notification.objects.create(
                        title="Grade Published",
                        message=f"Grades have been uploaded for {title}.",
                        type="grade",
                        url=reverse('student_grades')
                    )

                    notif.users.add(student.user)
                    notified_student_ids.add(student.id)

            except Student.DoesNotExist:
                print("❌ Student NOT FOUND:", reg_no)

        return redirect('upload_grades')

    return render(request, 'upload_grades.html')

@login_required
def student_grades(request):
    student = request.user.student_profile  # safe direct access

    grades = StudentGrade.objects.filter(
        student=student
    ).select_related('upload').order_by('-id')

    return render(request, 'student_grades.html', {
        'grades': grades
    })


@login_required
@role_required('ClassRep')
def cr_dashboard(request):
    return render(request, 'cr_dashboard.html')

def is_classrep(user):
    return user.groups.filter(name='ClassRep').exists()



@login_required
@role_required('ClassRep')
def create_assignment(request):

    student = getattr(request.user, 'student_profile', None)

    if not student:
        messages.error(request, "Student profile not found.")
        return redirect('cr_dashboard')

    if request.method == 'POST':

        title = request.POST.get('title')
        description = request.POST.get('description')
        subject_id = request.POST.get('subject')
        due_date = request.POST.get('due_date')
        file = request.FILES.get('file')

        # Create assignment
        new_assignment = Assignment.objects.create(
            title=title,
            description=description,
            subject_id=subject_id,
            batch=student.batch,
            due_date=due_date,
            file=file
        )

        # Notify students in this batch
        batch_students = Student.objects.filter(
            batch=student.batch
        ).select_related('user')

        target_users = [
            s.user for s in batch_students
            if s.user
        ]

        if target_users:

            assign_notif = Notification.objects.create(
                title="New Assignment",
                message=f"{title} has been posted.",
                type="assignment",
                url=reverse('assignment_list')
            )

            assign_notif.users.add(*target_users)

        messages.success(
            request,
            "Assignment created successfully and students notified."
        )

        return redirect('cr_dashboard')

    subjects = Subject.objects.all()

    return render(request, 'create_assignment.html', {
        'subjects': subjects,
        'batch': student.batch
    })

