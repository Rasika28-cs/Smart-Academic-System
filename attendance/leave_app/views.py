import json
import io
import csv
import pandas as pd
import qrcode
from datetime import date, datetime, timedelta

from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User, Group
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST

from .models import Student, LeaveRequest, Attendance, Notification, DefaulterStudent
from department.models import Staff, Achievement, Winner, Gallery, NewsItem, UpcomingEvent
from od.models import ODApplication


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


def is_class_incharge(user):
    return user.groups.filter(name='ClassIncharge').exists()

def is_mentor(user):
    return user.groups.filter(name='Mentor').exists()


# ─────────────────────────────────────────────
# HOME & LOGIN ROUTING
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

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            if next_url:
                return redirect(next_url)

            if user.is_superuser:
                return redirect('hod_dashboard')
            elif is_class_incharge(user):
                return redirect('class_incharge_dashboard')
            elif is_mentor(user):
                return redirect('mentor_dashboard')
            elif user.is_staff:
                return redirect('teacher_dashboard')
            else:
                return redirect('student_dashboard')

        # Legacy fallback
        try:
            student_obj = Student.objects.get(name=username)
            if student_obj.password and check_password(password, student_obj.password):
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


def logout_view(request):
    logout(request)
    return redirect('login_page')


# ─────────────────────────────────────────────
# DASHBOARDS (STUDENT, MENTOR, CI, TEACHER)
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
        'student': student,
        'total_leaves': total_leaves,
        'pending_leaves': pending_leaves,
        'attendance_percent': round(attendance_percent, 2),
        'present_classes': present_classes,
        'total_classes': total_classes,
    })


@login_required
def mentor_dashboard(request):
    if not is_mentor(request.user):
        return redirect('home')

    pending_leaves = LeaveRequest.objects.filter(status='Pending').count()
    pending_od = ODApplication.objects.filter(status='pending').count()

    context = {
        'pending_leaves': pending_leaves,
        'pending_od': pending_od,
        'total_notifications': pending_leaves + pending_od,
    }
    return render(request, 'mentor_dashboard.html', context)


@login_required
def class_incharge_dashboard(request):
    if not is_class_incharge(request.user):
        return redirect('home')

    # CI only sees what Mentor has already Approved
    pending_leaves = LeaveRequest.objects.filter(status='Mentor Approved').count()
    pending_od = ODApplication.objects.filter(status='pending').count()

    context = {
        'pending_leaves': pending_leaves,
        'pending_od': pending_od,
        'total_notifications': pending_leaves + pending_od,
        'total_students': Student.objects.count(),
        'total_defaulters': DefaulterStudent.objects.count(),
    }
    return render(request, 'class_incharge_dashboard.html', context)


@login_required
def teacher_dashboard(request):
    if not request.user.is_staff:
        return redirect('home')

    pending_leaves = LeaveRequest.objects.filter(status='Pending').count()
    pending_od = ODApplication.objects.filter(status='pending').count()
    total_notifications = pending_leaves + pending_od

    context = {
        'pending_leaves': pending_leaves,
        'pending_od': pending_od,
        'total_notifications': total_notifications
    }
    return render(request, 'teacher_dashboard.html', context)


# ─────────────────────────────────────────────
# LEAVE MANAGEMENT (NEW WORKFLOW)
# ─────────────────────────────────────────────

@login_required
def apply_page(request):
    student, err = _student_required(request)
    if err:
        return err
    return render(request, 'apply.html')


@login_required
def apply_leave_api(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error'})

    student, err = _student_required(request)
    if err:
        return JsonResponse({'status': 'error', 'message': 'Not logged in as student'})

    try:
        data = json.loads(request.body)
        from_date = datetime.strptime(data.get('from_date'), "%Y-%m-%d").date()
        to_date = datetime.strptime(data.get('to_date'), "%Y-%m-%d").date()
    except Exception:
        return JsonResponse({'status': 'error', 'message': 'Invalid date format'})

    leave = LeaveRequest.objects.create(
        student=student,
        from_date=from_date,
        to_date=to_date,
        reason=data.get('reason'),
        status='Pending',
    )

    # Notify Mentors only
    try:
        mentor_users = User.objects.filter(groups__name='Mentor')
        Notification.objects.create(
            title="New Leave Request",
            message=f"{student.name} applied leave",
            type="leave",
            url="/mentor/leaves/"
        ).users.set(mentor_users)
    except:
        pass

    return JsonResponse({'status': 'success'})


@login_required
def mentor_leaves(request):
    if not is_mentor(request.user):
        return redirect('home')

    # GET SELECTED YEAR/BATCH
    selected_batch = request.GET.get('batch')

    # GET PENDING LEAVES
    leaves = LeaveRequest.objects.filter(status='Pending')

    # FILTER BY BATCH
    if selected_batch:
        leaves = leaves.filter(student__batch=selected_batch)

    # GET ALL AVAILABLE BATCHES
    batches = Student.objects.values_list('batch', flat=True).distinct()

    return render(request, 'mentor_leaves.html', {
        'leaves': leaves,
        'batches': batches,
        'selected_batch': selected_batch,
    })
@login_required
def mentor_review_leave(request, leave_id, action):
    if not is_mentor(request.user):
        return redirect('home')

    try:
        leave = LeaveRequest.objects.get(id=leave_id)
    except LeaveRequest.DoesNotExist:
        return redirect('mentor_leaves')

    if action == 'approve':
        leave.status = 'Mentor Approved'

        # SAVE REVIEW DETAILS
        leave.mentor_reviewed_by = request.user
        leave.mentor_reviewed_at = timezone.now()

    elif action == 'reject':
        leave.status = 'Rejected'

        # SAVE REVIEW DETAILS
        leave.mentor_reviewed_by = request.user
        leave.mentor_reviewed_at = timezone.now()

    leave.save()
    return redirect('mentor_leaves')

@login_required
def ci_leaves(request):
    if not is_class_incharge(request.user):
        return redirect('home')

    # GET SELECTED YEAR/BATCH
    selected_batch = request.GET.get('batch')

    # GET ONLY MENTOR APPROVED LEAVES
    leaves = LeaveRequest.objects.filter(status='Mentor Approved')

    # FILTER BY BATCH
    if selected_batch:
        leaves = leaves.filter(student__batch=selected_batch)

    # GET ALL AVAILABLE BATCHES
    batches = Student.objects.values_list('batch', flat=True).distinct()

    return render(request, 'ci_leaves.html', {
        'leaves': leaves,
        'batches': batches,
        'selected_batch': selected_batch,
    })

@login_required
def ci_review_leave(request, leave_id, action):
    if not is_class_incharge(request.user):
        return redirect('home')

    try:
        leave = LeaveRequest.objects.get(id=leave_id)
    except LeaveRequest.DoesNotExist:
        return redirect('ci_leaves')

    if action == 'approve':

        if leave.status == 'Mentor Approved':
            leave.status = 'Approved'

            # SAVE CI DETAILS
            leave.class_incharge_reviewed_by = request.user
            leave.class_incharge_reviewed_at = timezone.now()

            # AUTO ATTENDANCE
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

        # SAVE CI DETAILS
        leave.class_incharge_reviewed_by = request.user
        leave.class_incharge_reviewed_at = timezone.now()

    leave.save()
    return redirect('ci_leaves')
# ─────────────────────────────────────────────
# ATTENDANCE & GENERAL STAFF VIEWS
# ─────────────────────────────────────────────

@login_required
def attendance(request):
    student, err = _student_required(request)
    if err:
        return err
    records = Attendance.objects.filter(student=student)
    return render(request, 'attendance.html', {'attendance': records})


@login_required
def leave_status(request):
    student, err = _student_required(request)
    if err:
        return err
    leaves = LeaveRequest.objects.filter(student=student)
    return render(request, 'leave_status.html', {'leaves': leaves})


@login_required
def student_leaves(request):
    student, err = _student_required(request)
    if err:
        return err
    leaves = LeaveRequest.objects.filter(student=student)
    return render(request, 'student_leaves.html', {'leaves': leaves})


@login_required
def view_students(request):
    if not request.user.is_staff:
        return redirect('home')
    students = Student.objects.all()
    return render(request, 'view_students.html', {'students': students})


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

    attendance_records = Attendance.objects.filter(date=today)
    attendance_map = {att.student_id: att.status for att in attendance_records}

    student_data = []
    for student in students:
        status = attendance_map.get(student.id, 'Present')
        student_data.append({'student': student, 'status': status})

    return render(request, 'mark_attendance.html', {'student_data': student_data})


@login_required
def update_leave_status(request, leave_id, action):
    """Legacy single-step approval for generic staff if needed."""
    if not request.user.is_staff:
        return redirect('home')

    try:
        leave = LeaveRequest.objects.get(id=leave_id)
    except LeaveRequest.DoesNotExist:
        return redirect('today_leaves')

    if action == 'approve':
        leave.status = 'Approved'
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


@login_required
def today_leaves(request):
    if not request.user.is_staff:
        return redirect('home')

    today = date.today()

    selected_batch = request.GET.get('batch')

    leaves = LeaveRequest.objects.filter(
        from_date__lte=today,
        to_date__gte=today
    )

    if selected_batch:
        leaves = leaves.filter(student__batch=selected_batch)

    batches = Student.objects.values_list(
        'batch',
        flat=True
    ).distinct()

    return render(request, 'today_leaves.html', {
        'leaves': leaves,
        'batches': batches,
        'selected_batch': selected_batch,
    })
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

    if search_query:
        student_data = [s for s in student_data if search_query.lower() in s['name'].lower() or search_query.lower() in s['roll_no'].lower()]

    if sort_order == 'low':
        student_data = sorted(student_data, key=lambda x: x['percentage'])

    names = [s['name'] for s in student_data]
    percentages = [s['percentage'] for s in student_data]

    daily_records = []
    if selected_date:
        for record in Attendance.objects.filter(date=selected_date):
            daily_records.append({'name': record.student.name, 'roll_no': record.student.roll_no, 'status': record.status})

    return render(request, 'hod_dashboard.html', {
        'students': student_data,
        'names': names,
        'percentages': percentages,
        'search_query': search_query,
        'selected_date': selected_date,
        'daily_records': daily_records,
    })


# ─────────────────────────────────────────────
# UTILS (QR, CSV, CALC)
# ─────────────────────────────────────────────

def calculator(request):
    return render(request, 'calculator.html')


def generate_qr(request):
    url = request.build_absolute_uri(reverse('home'))
    img = qrcode.make(url)
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return HttpResponse(buffer.getvalue(), content_type='image/png')


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
# NOTIFICATIONS
# ─────────────────────────────────────────────

@login_required
def notification_count(request):
    if not request.user.is_staff:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    pending_leaves = LeaveRequest.objects.filter(status='Pending')
    pending_od = ODApplication.objects.filter(status='pending')
    total = pending_leaves.count() + pending_od.count()

    latest_leave = pending_leaves.order_by('-id').first()
    latest_od = pending_od.order_by('-id').first()

    latest = None
    if latest_leave and latest_od:
        latest = latest_leave if latest_leave.id > latest_od.id else latest_od
    else:
        latest = latest_leave or latest_od

    latest_message = ""
    latest_id = 0
    latest_url = ""

    if latest:
        if isinstance(latest, LeaveRequest):
            latest_message = f"{latest.student.name} applied leave"
            latest_url = f"/leave/update/{latest.id}/"
        else:
            latest_message = f"{latest.student.username} applied OD"
            latest_url = f"/od/update/{latest.id}/"
        latest_id = latest.id

    notifications = []
    for leave in pending_leaves.order_by('-id')[:10]:
        notifications.append({"id": leave.id, "title": "Leave Request", "message": leave.reason, "type": "leave"})
    for od in pending_od.order_by('-id')[:10]:
        notifications.append({"id": od.id, "title": "OD Request", "message": "OD Event", "type": "od"})

    return JsonResponse({"total": total, "message": latest_message, "latest_id": latest_id, "url": latest_url, "notifications": notifications})


@login_required
def get_notifications(request):
    notifications = Notification.objects.filter(users=request.user).order_by('-id')
    unread = notifications.exclude(read_by=request.user)
    latest = unread.first()
    data = {
        "total": unread.count(),
        "latest_id": latest.id if latest else 0,
        "message": latest.message if latest else "",
        "url": latest.url if latest else "",
        "notifications": [{"id": n.id, "title": n.title, "message": n.message, "time": n.created_at.strftime("%d %b %I:%M %p"), "url": n.url, "read": request.user in n.read_by.all()} for n in notifications[:5]]
    }
    return JsonResponse(data)


@require_POST
@login_required
def mark_as_read(request, id):
    try:
        notif = Notification.objects.get(id=id)
        notif.read_by.add(request.user)
        return JsonResponse({"status": "ok"})
    except Notification.DoesNotExist:
        return JsonResponse({"status": "error"})


# ─────────────────────────────────────────────
# DEFAULTERS LOGIC
# ─────────────────────────────────────────────

@login_required
def upload_defaulters(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST only'})
    file = request.FILES.get('file')
    if not file:
        return JsonResponse({'status': 'error', 'message': 'No file uploaded'})
    try:
        df = pd.read_excel(file)
        df = df[df['Dept'] == 'CYSE']
        count = 0
        for _, row in df.iterrows():
            DefaulterStudent.objects.create(roll_no=row['Roll No'], name=row['Name'], staff_incharge=row['Staff Incharge'], department=row['Dept'], year=row['Year'], reason=row['Reason'])
            count += 1
        return JsonResponse({'status': 'success', 'message': f'{count} students uploaded'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})


def defaulter_list(request):
    students = DefaulterStudent.objects.all().order_by('year', 'roll_no')
    return render(request, 'defaulter_list.html', {'students': students})


@login_required
def upload_defaulters_manual(request):
    if request.method == 'POST':
        file = request.FILES.get('file')
        if not file:
            return redirect('defaulter_list')
        df = pd.read_excel(file)
        df.columns = df.columns.str.strip()
        df['Dept'] = df['Dept'].astype(str).str.strip().str.upper()
        df = df[df['Dept'] == 'CYSE']
        DefaulterStudent.objects.all().delete()
        for _, row in df.iterrows():
            DefaulterStudent.objects.create(roll_no=row['Roll No'], name=row['Name'], staff_incharge=row['Staff Incharge'], department=row['Dept'], year=row['Year'], reason=row['Reason'])
        return redirect('defaulter_list')
    return redirect('defaulter_list')


def update_action(request, id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error'})
    try:
        data = json.loads(request.body)
        action = data.get('action')
        student = DefaulterStudent.objects.get(id=id)
        student.action_taken = action
        student.save()
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})


@login_required
def student_defaulter_view(request):
    user = request.user
    students = DefaulterStudent.objects.filter(roll_no=user.username).order_by('year', 'roll_no')
    return render(request, 'student_defaulter.html', {'students': students})