import json
import io
import csv
import pandas as pd
import qrcode
from datetime import date, datetime, timedelta
from functools import wraps

from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User, Group
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db.models import Count, Q, Case, When, FloatField, F, ExpressionWrapper, Avg
from django.db.models.functions import Cast
from django.utils import timezone
from django.core.exceptions import PermissionDenied

# Models from your app
from .models import (
    Student, LeaveRequest, Attendance, Notification, DefaulterStudent,
    Department, Subject, Timetable, Assignment, Exam, Result, Circular, ActivityLog
)
# Models from existing related apps
from department.models import Staff, Achievement, Winner, Gallery, NewsItem, UpcomingEvent
from od.models import ODApplication


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


@login_required
def leave_status(request):
    student, err = _student_required(request)
    if err: return err
    leaves = LeaveRequest.objects.filter(student=student).order_by('-created_at')
    return render(request, 'leave_status.html', {'leaves': leaves})


@login_required
def apply_page(request):
    student, err = _student_required(request)
    if err: return err
    return render(request, 'apply.html')


@login_required
def student_defaulter_view(request):
    student, err = _student_required(request)
    if err: return err
    defaulters = DefaulterStudent.objects.filter(roll_no=student.roll_no).order_by('year')
    return render(request, 'student_defaulter.html', {'students': defaulters})


# ─────────────────────────────────────────────
# 4. HIERARCHICAL LEAVE CHAINING (THE NEW ENGINE)
# ─────────────────────────────────────────────

@login_required
def apply_leave_api(request):
    """Workflow Stage 0: Submission"""
    if request.method != 'POST': return JsonResponse({'status': 'error'})
    student, err = _student_required(request)
    if err: return JsonResponse({'status': 'error', 'message': 'Not logged in as student'})

    try:
        data = json.loads(request.body)
        leave = LeaveRequest.objects.create(
            student=student,
            from_date=datetime.strptime(data.get('from_date'), "%Y-%m-%d").date(),
            to_date=datetime.strptime(data.get('to_date'), "%Y-%m-%d").date(),
            reason=data.get('reason'),
            status='PENDING_MENTOR'
        )
        
        # Notify Mentor
        if student.mentor:
            notif = Notification.objects.create(
                title="New Leave Request",
                message=f"{student.name} applied for leave. Stage: Mentor Review.",
                type="leave",
                url="/mentor/leaves/"
            )
            notif.users.add(student.mentor)
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})


@login_required
@role_required('Mentor')
def mentor_dashboard(request):
    pending_leaves = LeaveRequest.objects.filter(status='PENDING_MENTOR')
    if not request.user.is_superuser:
        pending_leaves = pending_leaves.filter(student__mentor=request.user)
    
    pending_od = ODApplication.objects.filter(status='pending').count()
    context = {
        'leaves': pending_leaves,
        'pending_leaves_count': pending_leaves.count(),
        'pending_od': pending_od,
        'total_notifications': pending_leaves.count() + pending_od,
    }
    return render(request, 'mentor_dashboard.html', context)


@login_required
@role_required('Mentor')
def mentor_review_leave(request, leave_id, action):
    """Workflow Stage 1: Mentor Review -> Forward to CI"""
    leave = get_object_or_404(LeaveRequest, id=leave_id)
    
    if action == 'approve':
        leave.status = 'PENDING_CLASSINCHARGE'
        leave.mentor_reviewed_by = request.user
        leave.mentor_reviewed_at = timezone.now()
        
        # Notify CI Group
        ci_users = User.objects.filter(groups__name='ClassIncharge')
        notif = Notification.objects.create(
            title="Leave Forwarded",
            message=f"Mentor approved {leave.student.name}'s leave. Pending Final Review.",
            type="leave",
            url="/class-incharge/leaves/"
        )
        notif.users.set(ci_users)
    else:
        leave.status = 'REJECTED_BY_MENTOR'
        leave.mentor_reviewed_at = timezone.now()
    
    leave.save()
    messages.success(request, f"Leave {action}ed.")
    return redirect('mentor_dashboard')


@login_required
@role_required('ClassIncharge')
def class_incharge_dashboard(request):
    # CI sees what Mentor approved
    pending_leaves = LeaveRequest.objects.filter(status='PENDING_CLASSINCHARGE')
    pending_od = ODApplication.objects.filter(status='pending').count()

    context = {
        'leaves': pending_leaves,
        'pending_leaves_count': pending_leaves.count(),
        'pending_od': pending_od,
        'total_notifications': pending_leaves.count() + pending_od,
        'total_students': Student.objects.count(),
        'total_defaulters': DefaulterStudent.objects.count(),
    }
    return render(request, 'class_incharge_dashboard.html', context)


@login_required
@role_required('ClassIncharge')
def ci_review_leave(request, leave_id, action):
    """Workflow Stage 2: Final Approval + Auto Attendance"""
    leave = get_object_or_404(LeaveRequest, id=leave_id)
    
    if action == 'approve':
        leave.status = 'APPROVED'
        leave.class_incharge_reviewed_by = request.user
        leave.class_incharge_reviewed_at = timezone.now()
        
        # AUTO ATTENDANCE LOGIC
        curr = leave.from_date
        while curr <= leave.to_date:
            Attendance.objects.update_or_create(
                student=leave.student,
                date=curr,
                defaults={'status': 'Leave'}
            )
            curr += timedelta(days=1)
    else:
        leave.status = 'REJECTED'
        leave.class_incharge_reviewed_at = timezone.now()

    leave.save()
    messages.success(request, f"Leave finalized: {action}")
    return redirect('class_incharge_dashboard')


# ─────────────────────────────────────────────
# 5. STAFF & TEACHER VIEWS (LEGACY PRESERVED)
# ─────────────────────────────────────────────

@login_required
def teacher_dashboard(request):
    if not request.user.is_staff: return redirect('home')
    pending_leaves = LeaveRequest.objects.filter(status__icontains='PENDING').count()
    pending_od = ODApplication.objects.filter(status='pending').count()
    return render(request, 'teacher_dashboard.html', {
        'pending_leaves': pending_leaves,
        'pending_od': pending_od,
        'total_notifications': pending_leaves + pending_od
    })


@login_required
def mark_attendance(request):
    if not request.user.is_staff: return HttpResponse('Unauthorized', status=403)
    students = Student.objects.all().order_by('roll_no')
    today = date.today()

    if request.method == 'POST':
        for student in students:
            status = request.POST.get(f'status_{student.id}')
            if status:
                Attendance.objects.update_or_create(
                    student=student, date=today, defaults={'status': status}
                )
        messages.success(request, "Attendance marked for today.")
        return redirect('teacher_dashboard')

    records = Attendance.objects.filter(date=today)
    att_map = {r.student_id: r.status for r in records}
    student_data = [{'student': s, 'status': att_map.get(s.id, 'Present')} for s in students]
    return render(request, 'mark_attendance.html', {'student_data': student_data})


@login_required
def view_students(request):
    if not request.user.is_staff: return redirect('home')
    students = Student.objects.all().order_by('roll_no')
    return render(request, 'view_students.html', {'students': students})


@login_required
def today_leaves(request):
    if not request.user.is_staff: return redirect('home')
    today = date.today()
    selected_batch = request.GET.get('batch')
    leaves = LeaveRequest.objects.filter(from_date__lte=today, to_date__gte=today)
    if selected_batch:
        leaves = leaves.filter(student__batch=selected_batch)
    batches = Student.objects.values_list('batch', flat=True).distinct()
    return render(request, 'today_leaves.html', {'leaves': leaves, 'batches': batches, 'selected_batch': selected_batch})


# ─────────────────────────────────────────────
# 6. HOD DASHBOARD & ANALYTICS (OPTIMIZED)
# ─────────────────────────────────────────────

@login_required
@role_required('HOD')
def hod_dashboard(request):
    search_query = request.GET.get('search', '')
    sort_order = request.GET.get('sort', '')
    selected_date = request.GET.get('date')

    # Optimized Query with Aggregation
    students = Student.objects.annotate(
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
            When(total__gt=0, then=(F('weighted_score') / Cast(F('total'), FloatField())) * 100),
            default=0.0, output_field=FloatField()
        )
    ).order_by('-perc')

    if search_query:
        students = students.filter(Q(name__icontains=search_query) | Q(roll_no__icontains=search_query))
    
    if sort_order == 'low':
        students = students.order_by('perc')

    # For Chart.js
    names = [s.name for s in students[:15]]
    percentages = [round(s.perc, 2) for s in students[:15]]

    daily_records = []
    if selected_date:
        daily_records = Attendance.objects.filter(date=selected_date).select_related('student')

    return render(request, 'hod_dashboard.html', {
        'students': students,
        'names': names,
        'percentages': percentages,
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
    return render(request, 'defaulter_list.html', {'students': students})


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
    student, _ = _student_required(request)
    data = Assignment.objects.filter(batch=student.batch).order_by('-due_date')
    return render(request, 'assignments.html', {'assignments': data})


@login_required
def student_results(request):
    student, _ = _student_required(request)
    results = Result.objects.filter(student=student).select_related('exam__subject')
    return render(request, 'results.html', {'results': results})

# OD Integration
@login_required
def view_od_status(request):
    ods = ODApplication.objects.filter(student_user=request.user)
    return render(request, 'od_status.html', {'ods': ods})