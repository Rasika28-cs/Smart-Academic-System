import json
import io
import csv
from datetime import date

import qrcode

from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .models import Student, LeaveRequest, Attendance
from department.models import Staff, Achievement, Winner, Gallery, NewsItem, UpcomingEvent

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _get_student(request):
    """Return the Student linked to the logged-in Django user, or None."""
    try:
        return request.user.student_profile
    except (AttributeError, Student.DoesNotExist):
        return None


def _student_required(request):
    """
    Returns (student, None) on success.
    Returns (None, redirect_response) when access should be denied.
    """
    if not request.user.is_authenticated:
        return None, redirect('login_page')
    student = _get_student(request)
    if student is None:
        return None, redirect('login_page')
    return student, None


# ─────────────────────────────────────────────
# HOME
# ─────────────────────────────────────────────

def home(request):
    # Redirect authenticated users to their dashboard
    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser:
            return redirect('hod_dashboard')
        student = _get_student(request)
        if student:
            return redirect('student_dashboard')
        return redirect('teacher_dashboard')

    # Public view — fetch department + homepage data
    context = {
        'staff': Staff.objects.all(),
        'achievements': Achievement.objects.all(),
        'winners': Winner.objects.all(),
        'gallery_images': Gallery.objects.all()[:12],
        'news_items': NewsItem.objects.filter(is_active=True)[:20],
        'upcoming_events': UpcomingEvent.objects.filter(is_active=True)[:20],
    }
    return render(request, 'index.html', context)


# ─────────────────────────────────────────────
# STUDENT SIGNUP
# ─────────────────────────────────────────────

def signup_page(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        roll_no = request.POST.get('roll_no', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')

        # ── Validation ──────────────────────────────
        if not name or not roll_no:
            return render(request, 'signup.html', {'error': 'Name and Roll No are required'})

        if password != confirm_password:
            return render(request, 'signup.html', {'error': 'Passwords do not match'})

        if Student.objects.filter(roll_no=roll_no).exists():
            return render(request, 'signup.html', {'error': 'Roll number already registered'})

        if User.objects.filter(username=roll_no).exists():
            return render(request, 'signup.html', {'error': 'Roll number already registered'})

        # ── Create Django User (username = roll_no) ─
        django_user = User.objects.create_user(
            username=roll_no,
            password=password,
            first_name=name,
        )

        # ── Create Student profile ───────────────────
        Student.objects.create(
            user=django_user,
            name=name,
            roll_no=roll_no,
            password=make_password(password),  # legacy field kept
        )

        return redirect('login_page')

    return render(request, 'signup.html')


# ─────────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────────

def login_page(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        next_url = request.POST.get('next') or request.GET.get('next')

        # ── Try Django auth (works for students whose username=roll_no,
        #    teachers and HOD whose username is set by admin) ──────────
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            if next_url:
                return redirect(next_url)

            # Route by role
            if user.is_superuser:
                return redirect('hod_dashboard')
            elif user.is_staff:
                return redirect('teacher_dashboard')
            else:
                # Regular user → must be a student
                return redirect('student_dashboard')

        # ── Legacy fallback: student may have logged in by name before
        #    roll_no accounts existed.  Try matching name → look up roll_no
        #    then re-authenticate. ────────────────────────────────────────
        try:
            student_obj = Student.objects.get(name=username)
            # Verify against legacy hashed password stored on Student
            if student_obj.password and check_password(password, student_obj.password):
                # Ensure Django User exists and is linked
                if student_obj.user is None:
                    django_user, _ = User.objects.get_or_create(username=student_obj.roll_no)
                    django_user.set_password(password)
                    django_user.first_name = student_obj.name
                    django_user.save()
                    student_obj.user = django_user
                    student_obj.save()
                else:
                    django_user = student_obj.user

                login(request, django_user)

                if next_url:
                    return redirect(next_url)
                return redirect('student_dashboard')
        except Student.DoesNotExist:
            pass

        return render(request, 'login.html', {'error': 'Invalid credentials'})

    return render(request, 'login.html')


# ─────────────────────────────────────────────
# LOGOUT
# ─────────────────────────────────────────────

def logout_view(request):
    logout(request)
    return redirect('login_page')


# ─────────────────────────────────────────────
# STUDENT DASHBOARD
# ─────────────────────────────────────────────

@login_required
def dashboard(request):
    student, err = _student_required(request)
    if err:
        return err

    total_leaves = LeaveRequest.objects.filter(student=student).count()
    pending_leaves = LeaveRequest.objects.filter(student=student, status='Pending').count()

    records = Attendance.objects.filter(student=student)

    present_classes = records.filter(status='Present').count()
    leave_classes = records.filter(status='Leave').count()
    absent_classes = records.filter(status='Absent').count()

    total_classes = present_classes + leave_classes + absent_classes

    if total_classes > 0:
        score = (present_classes * 1) + (leave_classes * 0.99) + (absent_classes * 0.97)
        attendance_percent = (score / total_classes) * 100
    else:
        attendance_percent = 0

    return render(request, 'dashboard.html', {
        'total_leaves': total_leaves,
        'pending_leaves': pending_leaves,
        'attendance_percent': round(attendance_percent, 2),
    })


# ─────────────────────────────────────────────
# APPLY LEAVE (page)
# ─────────────────────────────────────────────

@login_required
def apply_page(request):
    student, err = _student_required(request)
    if err:
        return err
    return render(request, 'apply.html')


# ─────────────────────────────────────────────
# APPLY LEAVE (API)
# ─────────────────────────────────────────────




from datetime import datetime
import json
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import LeaveRequest


def assign_batch():
    current_hour = datetime.now().hour

    if 6 <= current_hour < 8:
        return 1
    elif 8 <= current_hour < 9:
        return 2
    return None


@login_required
def apply_leave_api(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error'})

    student, err = _student_required(request)
    if err:
        return JsonResponse({'status': 'error', 'message': 'Not logged in as student'})

    data = json.loads(request.body)

    # ✅ Convert string → date
    try:
        from_date = datetime.strptime(data.get('from_date'), "%Y-%m-%d").date()
        to_date = datetime.strptime(data.get('to_date'), "%Y-%m-%d").date()
    except Exception:
        return JsonResponse({'status': 'error', 'message': 'Invalid date format'})

    # ✅ Assign batch
    batch = assign_batch()

    LeaveRequest.objects.create(
        student=student,
        from_date=from_date,
        to_date=to_date,
        reason=data.get('reason'),
        status='Pending',
        batch_slot=batch,          # 🔥 NEW
        email_sent=False           # 🔥 IMPORTANT
    )
    LeaveRequest.objects.filter(
    created_at__hour__gte=6,
    created_at__hour__lt=8,
    email_sent=False
)

    return JsonResponse({'status': 'success'})
@shared_task
def send_leave_batch_1():
    requests = LeaveRequest.objects.filter(
        batch_slot=1,
        email_sent=False
    )

    if not requests.exists():
        return

    content = ""
    for r in requests:
        content += f"{r.student.name} ({r.student.roll_no}) | {r.from_date} - {r.to_date}\n"

    send_mailjet_email("Leave Requests (6–8 AM)", content)

    requests.update(email_sent=True)
@shared_task
def send_leave_batch_2():
    requests = LeaveRequest.objects.filter(
        batch_slot=2,
        email_sent=False
    )

    if not requests.exists():
        return

    content = ""
    for r in requests:
        content += f"{r.student.name} ({r.student.roll_no}) | {r.from_date} - {r.to_date}\n"

    send_mailjet_email("Leave Requests (8–9 AM)", content)

    requests.update(email_sent=True)
# ─────────────────────────────────────────────
# ATTENDANCE
# ─────────────────────────────────────────────

@login_required
def attendance(request):
    student, err = _student_required(request)
    if err:
        return err

    records = Attendance.objects.filter(student=student)
    return render(request, 'attendance.html', {'attendance': records})


# ─────────────────────────────────────────────
# LEAVE STATUS
# ─────────────────────────────────────────────

@login_required
def leave_status(request):
    student, err = _student_required(request)
    if err:
        return err

    leaves = LeaveRequest.objects.filter(student=student)
    return render(request, 'leave_status.html', {'leaves': leaves})


# ─────────────────────────────────────────────
# STUDENT LEAVES (alternate view)
# ─────────────────────────────────────────────

@login_required
def student_leaves(request):
    student, err = _student_required(request)
    if err:
        return err

    leaves = LeaveRequest.objects.filter(student=student)
    return render(request, 'student_leaves.html', {'leaves': leaves})


# ─────────────────────────────────────────────
# TEACHER DASHBOARD
# ─────────────────────────────────────────────

@login_required
def teacher_dashboard(request):
    if not request.user.is_staff:
        return redirect('home')
    return render(request, 'teacher_dashboard.html')


# ─────────────────────────────────────────────
# VIEW STUDENTS
# ─────────────────────────────────────────────

@login_required
def view_students(request):
    if not request.user.is_staff:
        return redirect('home')

    students = Student.objects.all()
    return render(request, 'view_students.html', {'students': students})


# ─────────────────────────────────────────────
# MARK ATTENDANCE
# ─────────────────────────────────────────────

from datetime import date

@login_required
def mark_attendance(request):
    if not request.user.is_staff:
        return HttpResponse('Only Teachers Allowed', status=403)

    students = Student.objects.all()
    today = date.today()

    if request.method == 'POST':
        for student in students:
            status = request.POST.get(f'status_{student.id}')
            if status:
                Attendance.objects.update_or_create(
                    student=student,
                    date=today,
                    defaults={'status': status}
                )
        return redirect('teacher_dashboard')

    # 🔥 Create list with status (no template filter needed)
    attendance_records = Attendance.objects.filter(date=today)
    attendance_map = {att.student_id: att.status for att in attendance_records}

    student_data = []
    for student in students:
        status = attendance_map.get(student.id, 'Present')  # default Present
        student_data.append({
            'student': student,
            'status': status
        })

    return render(request, 'mark_attendance.html', {
        'student_data': student_data
    })

# ─────────────────────────────────────────────
# UPDATE LEAVE STATUS (Teacher action)
# ─────────────────────────────────────────────

from datetime import timedelta

@login_required
def update_leave_status(request, leave_id, action):
    if not request.user.is_staff:
        return redirect('home')

    leave = LeaveRequest.objects.get(id=leave_id)

    if action == 'approve':
        leave.status = 'Approved'

        # 🔥 AUTO MARK ATTENDANCE AS LEAVE
        current_date = leave.from_date
        while current_date <= leave.to_date:
            Attendance.objects.update_or_create(
                student=leave.student,
                date=current_date,
                defaults={'status': 'Leave'}
            )
            current_date += timedelta(days=1)

    elif action == 'reject':
        leave.status = 'Rejected'

    leave.save()
    return redirect('today_leaves')

# ─────────────────────────────────────────────
# TODAY'S LEAVES (Teacher view)
# ─────────────────────────────────────────────

@login_required
def today_leaves(request):
    if not request.user.is_staff:
        return redirect('home')

    today = date.today()
    leaves = LeaveRequest.objects.filter(from_date__lte=today, to_date__gte=today)
    return render(request, 'today_leaves.html', {'leaves': leaves})


# ─────────────────────────────────────────────
# HOD DASHBOARD
# ─────────────────────────────────────────────

@login_required
def hod_dashboard(request):
    if not request.user.is_superuser:
        return redirect('login_page')

    students = Student.objects.all()
    search_query = request.GET.get('search', '')
    sort_order = request.GET.get('sort', '')
    selected_date = request.GET.get('date')

    student_data = []

    for student in students:
        records = Attendance.objects.filter(student=student)

        present = records.filter(status='Present').count()
        leave = records.filter(status='Leave').count()
        absent = records.filter(status='Absent').count()

        total = present + leave + absent

        if total > 0:
            score = (present * 1) + (leave * 0.99) + (absent * 0.97)
            percentage = (score / total) * 100
        else:
            percentage = 0

        student_data.append({
            'name': student.name,
            'roll_no': student.roll_no,
            'percentage': round(percentage, 2),
        })

    # 🔍 Search
    if search_query:
        student_data = [
            s for s in student_data
            if search_query.lower() in s['name'].lower()
            or search_query.lower() in s['roll_no'].lower()
        ]

    # 🔽 Sort
    if sort_order == 'low':
        student_data = sorted(student_data, key=lambda x: x['percentage'])

    # 📊 Chart
    names = [s['name'] for s in student_data]
    percentages = [s['percentage'] for s in student_data]

    # 📅 Daily report
    daily_records = []
    if selected_date:
        for record in Attendance.objects.filter(date=selected_date):
            daily_records.append({
                'name': record.student.name,
                'roll_no': record.student.roll_no,
                'status': record.status,
            })

    return render(request, 'hod_dashboard.html', {
        'students': student_data,
        'names': names,
        'percentages': percentages,
        'search_query': search_query,
        'selected_date': selected_date,
        'daily_records': daily_records,
    })


# ─────────────────────────────────────────────
# CALCULATOR
# ─────────────────────────────────────────────

def calculator(request):
    return render(request, 'calculator.html')


# ─────────────────────────────────────────────
# QR CODE
# ─────────────────────────────────────────────

def generate_qr(request):
    url = request.build_absolute_uri(reverse('home'))
    img = qrcode.make(url)
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return HttpResponse(buffer.getvalue(), content_type='image/png')


# ─────────────────────────────────────────────
# UPLOAD ATTENDANCE (CSV)
# ─────────────────────────────────────────────

def upload_attendance(request):
    if request.method == 'POST':
        file = request.FILES.get('file')

        if not file:
            messages.error(request, 'No file uploaded')
            return render(request, 'upload.html')

        try:
            decoded = file.read().decode('utf-8').splitlines()
            reader = csv.DictReader(decoded)
            count = 0

            for row in reader:
                roll_no = row.get('student_roll')
                row_date = row.get('date')
                status = row.get('status')

                try:
                    student = Student.objects.get(roll_no=roll_no)
                    if not Attendance.objects.filter(student=student, date=row_date).exists():
                        Attendance.objects.create(student=student, date=row_date, status=status)
                        count += 1
                except Student.DoesNotExist:
                    continue

            messages.success(request, f'{count} records uploaded successfully!')

        except Exception as e:
            messages.error(request, f'Error: {str(e)}')

    return render(request, 'upload.html')

