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
    return render(request, 'index.html')


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

    total_classes = Attendance.objects.filter(student=student).count()
    present_classes = Attendance.objects.filter(student=student, status='Present').count()

    attendance_percent = (present_classes / total_classes * 100) if total_classes > 0 else 0

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

@login_required
def apply_leave_api(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error'})

    student, err = _student_required(request)
    if err:
        return JsonResponse({'status': 'error', 'message': 'Not logged in as student'})

    data = json.loads(request.body)

    LeaveRequest.objects.create(
        student=student,
        from_date=data.get('from_date'),
        to_date=data.get('to_date'),
        reason=data.get('reason'),
        status='Pending',
    )

    return JsonResponse({'status': 'success'})


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

@login_required
def mark_attendance(request):
    if not request.user.is_staff:
        return HttpResponse('Only Teachers Allowed', status=403)

    students = Student.objects.all()

    if request.method == 'POST':
        today = date.today()
        for student in students:
            status = request.POST.get(f'status_{student.id}')
            if status and not Attendance.objects.filter(student=student, date=today).exists():
                Attendance.objects.create(student=student, date=today, status=status)
        return redirect('teacher_dashboard')

    return render(request, 'mark_attendance.html', {'students': students})


# ─────────────────────────────────────────────
# UPDATE LEAVE STATUS (Teacher action)
# ─────────────────────────────────────────────

@login_required
def update_leave_status(request, leave_id, action):
    if not request.user.is_staff:
        return redirect('home')

    leave = LeaveRequest.objects.get(id=leave_id)

    if action == 'approve':
        leave.status = 'Approved'
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
        total = Attendance.objects.filter(student=student).count()
        present = Attendance.objects.filter(student=student, status='Present').count()
        percentage = (present / total * 100) if total > 0 else 0
        student_data.append({
            'name': student.name,
            'roll_no': student.roll_no,
            'percentage': round(percentage, 2),
        })

    if search_query:
        student_data = [
            s for s in student_data
            if search_query.lower() in s['name'].lower()
            or search_query.lower() in s['roll_no'].lower()
        ]

    if sort_order == 'low':
        student_data = sorted(student_data, key=lambda x: x['percentage'])

    names = [s['name'] for s in student_data]
    percentages = [s['percentage'] for s in student_data]

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
