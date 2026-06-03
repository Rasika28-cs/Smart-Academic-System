import json
import io
import csv
import pandas as pd
import qrcode
from datetime import date, datetime, timedelta
from functools import wraps

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
    Department, Subject, Timetable, Assignment, AssignmentSubmission,
    ParentProfile, Exam, Result, Circular, ActivityLog
)
# Models from existing related apps
from department.models import Staff, Achievement, Winner, Gallery, NewsItem, UpcomingEvent
from od.models import ODApplication


from django.shortcuts import get_object_or_404, render
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.db import transaction
from django.contrib import messages
from .models import LeaveRequest

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


# ─────────────────────────────────────────────
# 3. STUDENT MODULES
# ─────────────────────────────────────────────

@login_required
def dashboard(request):
    student, err = _student_required(request)
    if err: return err

    total_leaves = LeaveRequest.objects.filter(student=student).count()
    pending_leaves = LeaveRequest.objects.filter(student=student, status__icontains='PENDING').count()
    records = Attendance.objects.filter(student=student)

    p = records.filter(status='Present').count()
    l = records.filter(status='Leave').count()
    a = records.filter(status='Absent').count()
    total_classes = p + l + a

    if total_classes > 0:
        score = (p * 1) + (l * 0.99) + (a * 0.97)
        attendance_percent = (score / total_classes) * 100
    else:
        attendance_percent = 0

    context = {
        'student': student,
        'total_leaves': total_leaves,
        'pending_leaves': pending_leaves,
        'attendance_percent': round(attendance_percent, 2),
        'present_classes': p,
        'total_classes': total_classes,
        'upcoming_assignments': Assignment.objects.filter(batch=student.batch, due_date__gte=timezone.now()),
        'today_timetable': Timetable.objects.filter(batch=student.batch, day=date.today().strftime('%a'))
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
    Helper function to determine if a student has an approved leave 
    covering the specified check_date.
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

    return render(request, 'teacher_dashboard.html', {
        'pending_leaves': LeaveRequest.objects.filter(status__icontains='PENDING').count(),
        'pending_od': ODApplication.objects.filter(status='pending').count()
    })


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
            leave = LeaveRequest.objects.select_for_update().get(id=leave_id)

            is_mentor = leave.student.mentor == user
            is_ci = leave.student.class_incharge == user

            if not (is_mentor or is_ci or user.is_superuser):
                raise PermissionDenied()

            if is_mentor and leave.status != 'PENDING':
                return _redirect_after_review(user, leave)

            if is_ci and leave.status != 'APPROVED_BY_MENTOR':
                return _redirect_after_review(user, leave)

            if action == 'approve':

                if is_mentor:
                    leave.status = 'APPROVED_BY_MENTOR'
                    msg = "Approved by Mentor, pending Class Incharge"
                else:
                    leave.status = 'APPROVED'

                    curr = leave.from_date
                    while curr <= leave.to_date:
                        day = curr.strftime('%a')
                        timetable = Timetable.objects.filter(
                            batch=leave.student.batch,
                            department=leave.student.department,
                            day=day
                        )

                        for t in timetable:
                            Attendance.objects.update_or_create(
                                student=leave.student,
                                subject=t.subject,
                                date=curr,
                                defaults={'status': 'Leave'}
                            )
                        curr += timedelta(days=1)

                    msg = "Final approval completed"

            else:
                leave.status = 'REJECTED'
                msg = "Leave rejected"

            leave.reviewed_by = user
            leave.reviewed_at = timezone.now()
            leave.save()

            Notification.objects.create(
                title="Leave Update",
                message=msg,
                type="leave",
                url="/leave-status/"
            ).users.add(leave.student.user)

            ActivityLog.objects.create(
                user=user,
                action=f"{action.upper()} leave {leave.id}",
                ip_address=request.META.get('REMOTE_ADDR')
            )

    except LeaveRequest.DoesNotExist:
        raise Http404()

    return _redirect_after_review(user, leave)


# ─────────────────────────────
# ATTENDANCE
# ─────────────────────────────
@login_required
def mark_attendance(request):
    if not request.user.is_staff:
        return HttpResponse('Unauthorized', status=403)

    students = Student.objects.all().order_by('roll_no')
    today = date.today()

    # Query all students who have approved leave covering today's date
    students_on_leave_ids = set(
        LeaveRequest.objects.filter(
            from_date__lte=today,
            to_date__gte=today,
            status='APPROVED'
        ).values_list('student_id', flat=True)
    )

    # Fetch existing today's attendance records to prevent redundant creations
    existing_attendances = {
        att.student_id: att for att in Attendance.objects.filter(date=today)
    }

    # Automatically create/update records for students with active approved leave
    for student_id in students_on_leave_ids:
        att = existing_attendances.get(student_id)
        if not att:
            new_att = Attendance.objects.create(
                student_id=student_id,
                date=today,
                status='Leave'
            )
            existing_attendances[student_id] = new_att
        elif att.status != 'Leave':
            att.status = 'Leave'
            att.save(update_fields=['status'])

    if request.method == 'POST':
        for s in students:
            # Skip students on approved leave to preserve their Leave state
            if s.id in students_on_leave_ids:
                continue

            status = request.POST.get(f'status_{s.id}')
            if status:
                Attendance.objects.update_or_create(
                    student=s,
                    date=today,
                    defaults={'status': status}
                )

        messages.success(request, "Attendance marked")
        return redirect('teacher_dashboard')

    # Build response dataset for safe UI rendering
    student_data = []
    for s in students:
        is_on_leave = s.id in students_on_leave_ids
        
        if is_on_leave:
            current_status = 'Leave'
        elif s.id in existing_attendances:
            current_status = existing_attendances[s.id].status
        else:
            current_status = 'Present'

        student_data.append({
            'student': s,
            'status': current_status,
            'is_on_leave': is_on_leave
        })

    return render(request, 'mark_attendance.html', {
        'student_data': student_data
    })


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
    students = Student.objects.filter(department=managed_dept).annotate(
        total=Count('attendance'),
        p=Count('attendance', filter=Q(attendance__status='Present')),
        l=Count('attendance', filter=Q(attendance__status='Leave')),
        a=Count('attendance', filter=Q(attendance__status='Absent')),
    ).annotate(
        weighted_score=ExpressionWrapper(
            (F('p') * 1.0) + (F('l') * 0.99) + (F('a') * 0.97),
            output_field=FloatField()
        )
    ).annotate(
        perc=Case(
            When(
                total__gt=0,
                then=(F('weighted_score') / Cast(F('total'), FloatField())) * 100
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
    return render(request, 'hod_dashboard.html', {
        'students': students,
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
    })

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
    if request.method != 'POST': return JsonResponse({'status': 'error'})
    file = request.FILES.get('file')
    try:
        df = pd.read_excel(file)
        df.columns = df.columns.str.strip()
        df = df[df['Dept'] == 'CYSE']
        for _, row in df.iterrows():
            DefaulterStudent.objects.create(
                roll_no=row['Roll No'], name=row['Name'], 
                staff_incharge=row['Staff Incharge'], department=row['Dept'], 
                year=row['Year'], reason=row['Reason']
            )
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})


def defaulter_list(request):
    students = DefaulterStudent.objects.all().order_by('year', 'roll_no')
    return render(request, 'defaulter_list.html', {'students': defaulter_list})


@login_required
def update_action(request, id):
    if request.method != 'POST': return JsonResponse({'status': 'error'})
    try:
        data = json.loads(request.body)
        std = DefaulterStudent.objects.get(id=id)
        std.action_taken = data.get('action')
        std.save()
        return JsonResponse({'status': 'success'})
    except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)})


# ─────────────────────────────────────────────
# 9. NEW ACADEMIC MODULES
# ─────────────────────────────────────────────

@login_required
def view_timetable(request):
    student = _get_student(request)
    batch = student.batch if student else request.GET.get('batch')
    data = Timetable.objects.filter(batch=batch).order_by('start_time')
    return render(request, 'timetable.html', {'timetable': data, 'batch': batch})


@login_required
def assignment_list(request):
    student, err = _student_required(request)
    if err: return err
    data = Assignment.objects.filter(batch=student.batch).order_by('-due_date')
    return render(request, 'assignments.html', {'assignments': data})


@login_required
def student_results(request):
    student, err = _student_required(request)
    if err: return err
    results = Result.objects.filter(student=student).select_related('exam__subject')
    return render(request, 'results.html', {'results': results})

# OD Integration
@login_required
def view_od_status(request):
    ods = ODApplication.objects.filter(student_user=request.user)
    return render(request, 'od_status.html', {'ods': ods})

def dashboard_redirect(request):
    user = request.user

    if not user.is_authenticated:
        return redirect("login_page")

    groups = set(user.groups.values_list("name", flat=True))

    if "Mentor" in groups:
        return redirect("mentor_dashboard")

    if "ClassIncharge" in groups:
        return redirect("class_incharge_dashboard")

    return redirect("login_page")


@login_required
def parent_dashboard(request):
    try:
        parent_profile = request.user.parentprofile
        student = parent_profile.student
    except Exception:
        return redirect('login_page')

    attendance_records = Attendance.objects.filter(student=student).order_by('-date')[:10]
    results = Result.objects.filter(student=student).select_related('exam')

    return render(request, 'parent_dashboard.html', {
        'student': student,
        'attendance': attendance_records,
        'results': results
    })


# ─────────────────────────────────────────────
# 1. ASSIGNMENT SUBMISSION SYSTEM
# ─────────────────────────────────────────────

@login_required
def student_submit_assignment(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    student = getattr(request.user, 'student_profile', None)
    
    if not student or student.batch != assignment.batch:
        return HttpResponseForbidden("You are not eligible for this assignment.")

    if timezone.now() > assignment.due_date:
        messages.error(request, "Submission deadline has passed.")
        return redirect('assignment_list')

    if request.method == 'POST':
        file = request.FILES.get('submission_file')
        if not file:
            messages.error(request, "Please upload a file.")
            return redirect('assignment_list')

        submission, created = AssignmentSubmission.objects.update_or_create(
            assignment=assignment,
            student=student,
            defaults={'file': file, 'submitted_at': timezone.now()}
        )
        
        ActivityLog.objects.create(
            user=request.user,
            action=f"Submitted assignment: {assignment.title}",
            ip_address=request.META.get('REMOTE_ADDR')
        )
        messages.success(request, "Assignment submitted successfully.")
        return redirect('assignment_list')

    return render(request, 'submit_assignment.html', {'assignment': assignment})

@login_required
def teacher_view_submissions(request, assignment_id):
    if not request.user.is_staff:
        raise PermissionDenied
    assignment = get_object_or_404(Assignment, id=assignment_id)
    submissions = assignment.submissions.all().select_related('student')
    return render(request, 'teacher_submissions.html', {
        'assignment': assignment,
        'submissions': submissions
    })

@login_required
def teacher_grade_submission(request, submission_id):
    if not request.user.is_staff:
        raise PermissionDenied
    submission = get_object_or_404(AssignmentSubmission, id=submission_id)
    
    if request.method == 'POST':
        submission.marks = request.POST.get('marks')
        submission.feedback = request.POST.get('feedback')
        submission.save()
        
        notif = Notification.objects.create(
            title="Assignment Graded",
            message=f"Your assignment '{submission.assignment.title}' has been graded.",
            type="academic"
        )
        if submission.student.user:
            notif.users.add(submission.student.user)
            
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)

# ─────────────────────────────────────────────
# 2. PARENT PORTAL
# ─────────────────────────────────────────────

@login_required
def parent_login_redirect_dashboard(request):
    try:
        parent = request.user.parentprofile
        return render(request, 'parent_dashboard.html', {'student': parent.student})
    except ParentProfile.DoesNotExist:
        return redirect('home')

@login_required
def parent_view_attendance(request):
    parent = get_object_or_404(ParentProfile, user=request.user)
    records = Attendance.objects.filter(student=parent.student).order_by('-date')
    return render(request, 'parent_attendance.html', {'attendance': records, 'student': parent.student})

@login_required
def parent_view_results(request):
    parent = get_object_or_404(ParentProfile, user=request.user)
    results = Result.objects.filter(student=parent.student).select_related('exam__subject')
    return render(request, 'parent_results.html', {'results': results, 'student': parent.student})

@login_required
def parent_view_notifications(request):
    parent = get_object_or_404(ParentProfile, user=request.user)
    # Parents see notifications sent to their child's user account
    notifications = Notification.objects.filter(users=parent.student.user).order_by('-created_at')
    return render(request, 'parent_notifications.html', {'notifications': notifications})

# ─────────────────────────────────────────────
# 3. SEMESTER & PROMOTION SYSTEM
# ─────────────────────────────────────────────

@login_required
@role_required('HOD')
@transaction.atomic
def promote_students(request):
    if request.method == 'POST':
        current_batch = request.POST.get('current_batch')
        new_batch = request.POST.get('new_batch')
        
        students = Student.objects.filter(batch=current_batch)
        count = students.count()
        students.update(batch=new_batch)
        
        ActivityLog.objects.create(
            user=request.user,
            action=f"Promoted {count} students from {current_batch} to {new_batch}"
        )
        messages.success(request, f"Successfully promoted {count} students.")
        return redirect('hod_dashboard')
    
    batches = Student.objects.values_list('batch', flat=True).distinct()
    return render(request, 'promote_students.html', {'batches': batches})

@login_required
@role_required('HOD')
def view_promotion_status(request):
    stats = Student.objects.values('batch').annotate(student_count=Count('id')).order_by('batch')
    return render(request, 'promotion_status.html', {'stats': stats})

# ─────────────────────────────────────────────
# 4. TEACHER SUBJECT MAPPING SYSTEM
# ─────────────────────────────────────────────

@login_required
@role_required('HOD')
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
# 5. CIRCULAR DISTRIBUTION SYSTEM
# ─────────────────────────────────────────────

@login_required
@role_required('HOD', 'ClassIncharge')
def create_circular(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        content = request.POST.get('content')
        dept_id = request.POST.get('department')
        file = request.FILES.get('file')
        
        dept = Department.objects.get(id=dept_id) if dept_id else None
        circular = Circular.objects.create(
            title=title, content=content, department=dept, file=file
        )
        
        # Notify relevant students
        target_students = Student.objects.all()
        if dept:
            target_students = target_students.filter(department=dept)
            
        notif = Notification.objects.create(
            title="New Circular",
            message=title,
            type="circular",
            url=f"/circulars/{circular.id}/"
        )
        
        user_ids = target_students.values_list('user_id', flat=True)
        notif.users.add(*user_ids)
        
        messages.success(request, "Circular published and notifications sent.")
        return redirect('list_circulars')
        
    departments = Department.objects.all()
    return render(request, 'create_circular.html', {'departments': departments})

@login_required
def list_circulars(request):
    circulars = Circular.objects.all().order_by('-created_at')
    student = getattr(request.user, 'student_profile', None)
    if student:
        circulars = circulars.filter(Q(department=student.department) | Q(department__isnull=True))
    return render(request, 'circular_list.html', {'circulars': circulars})

@login_required
@role_required('HOD')
def delete_circular(request, id):
    circular = get_object_or_404(Circular, id=id)
    circular.delete()
    messages.success(request, "Circular deleted.")
    return redirect('list_circulars')

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

@login_required
@role_required('HOD')
def create_timetable_entry(request):
    if request.method == 'POST':
        day = request.POST.get('day')
        room = request.POST.get('room')
        start = request.POST.get('start_time')
        end = request.POST.get('end_time')
        teacher_id = request.POST.get('teacher')
        subject_id = request.POST.get('subject')
        batch = request.POST.get('batch')
        dept_id = request.POST.get('department')

        # Check Teacher Clash
        teacher_clash = Timetable.objects.filter(
            day=day,
            teacher_id=teacher_id,
            start_time__lt=end,
            end_time__gt=start
        ).exists()
        
        # Check Room Clash
        room_clash = Timetable.objects.filter(
            day=day,
            room=room,
            start_time__lt=end,
            end_time__gt=start
        ).exists()

        if teacher_clash:
            messages.error(request, "Teacher is already assigned to another class at this time.")
        elif room_clash:
            messages.error(request, "Room is already occupied at this time.")
        else:
            Timetable.objects.create(
                day=day,
                room=room,
                start_time=start,
                end_time=end,
                teacher_id=teacher_id,
                subject_id=subject_id,
                batch=batch,
                department_id=dept_id,
            )
            messages.success(request, "Timetable entry created.")
            
        return redirect('view_timetable')

    return render(request, 'create_timetable.html')