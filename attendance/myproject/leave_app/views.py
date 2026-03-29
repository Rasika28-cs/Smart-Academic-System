import json
import io
import qrcode
from datetime import datetime, date

from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required

from .models import Student, LeaveRequest, Attendance

# =====================================================
# HOME
# =====================================================

def home(request):
    return render(request, 'index.html')


# =====================================================
# STUDENT SIGNUP
# =====================================================

def signup_page(request):
    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        if password != confirm_password:
            return render(request, "signup.html", {"error": "Passwords do not match"})

        if Student.objects.filter(email=email).exists():
            return render(request, "signup.html", {"error": "Email already registered"})

        Student.objects.create(
            name=name,
            email=email,
            password=make_password(password)
        )

        return redirect("login_page")

    return render(request, "signup.html")


# =====================================================
# STUDENT LOGIN
# =====================================================

from django.contrib.auth.hashers import check_password

def login_page(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        # 🔥 capture next URL
        next_url = request.GET.get('next')

        # =========================
        # Django Auth (Teacher / HOD)
        # =========================
        user = authenticate(request, username=username, password=password)

        if user is not None:
            request.session.flush()   # 🔥 VERY IMPORTANT
            login(request, user)

            if next_url:
                return redirect(next_url)

            if user.is_superuser:
                return redirect("hod_dashboard")
            elif user.is_staff:
                return redirect("teacher_dashboard")

        # =========================
        # Student Login
        # =========================
        try:
            student = Student.objects.get(name=username)

            if check_password(password, student.password):
                request.session.flush()   # 🔥 VERY IMPORTANT
                request.session["student_id"] = student.id

                if next_url:
                    return redirect(next_url)

                return redirect("student_dashboard")

        except Student.DoesNotExist:
            pass

        return render(request, "login.html", {"error": "Invalid credentials"})

    return render(request, "login.html")
# =====================================================
# STUDENT DASHBOARD
# =====================================================

def dashboard(request):
    
    if not request.session.get("student_id"):
        return redirect("login_page")

    student_id = request.session.get("student_id")

    # Leave data
    total_leaves = LeaveRequest.objects.filter(student_id=student_id).count()
    pending_leaves = LeaveRequest.objects.filter(
        student_id=student_id,
        status="Pending"
    ).count()

    # Attendance calculation 🔥
    total_classes = Attendance.objects.filter(student_id=student_id).count()
    present_classes = Attendance.objects.filter(
        student_id=student_id,
        status="Present"
    ).count()

    if total_classes > 0:
        attendance_percent = (present_classes / total_classes) * 100
    else:
        attendance_percent = 0

    context = {
        "total_leaves": total_leaves,
        "pending_leaves": pending_leaves,
        "attendance_percent": round(attendance_percent, 2)
    }

    return render(request, "dashboard.html", context)
# =====================================================
# APPLY LEAVE
# =====================================================

def apply_page(request):
    if not request.session.get("student_id"):
        return redirect("login_page")
    return render(request, "apply.html")


def apply_leave_api(request):
    if request.method == "POST":
        if not request.session.get("student_id"):
            return JsonResponse({"status": "error", "message": "Not logged in"})

        data = json.loads(request.body)

        LeaveRequest.objects.create(
            student_id=request.session.get("student_id"),
            from_date=data.get("from_date"),
            to_date=data.get("to_date"),
            reason=data.get("reason"),
            status="Pending"
        )

        return JsonResponse({"status": "success"})

    return JsonResponse({"status": "error"})


# =====================================================
# STUDENT FEATURES
# =====================================================

def attendance(request):
    if not request.session.get("student_id"):
        return redirect("login_page")

    student = Student.objects.get(id=request.session.get("student_id"))
    records = Attendance.objects.filter(student=student)

    return render(request, "attendance.html", {"attendance": records})


def leave_status(request):
    if not request.session.get("student_id"):
        return redirect("login_page")

    student_id = request.session.get("student_id")
    leaves = LeaveRequest.objects.filter(student_id=student_id)

    return render(request, 'leave_status.html', {'leaves': leaves})

def logout_view(request):
    request.session.flush()   # 🔥 clears student session
    logout(request)           # 🔥 clears django auth
    return redirect("login_page")


# =====================================================
# TEACHER LOGIN (Django Auth)
# =====================================================




# =====================================================
# TEACHER DASHBOARD
# =====================================================

@login_required
def teacher_dashboard(request):
    if not request.user.is_staff:
        return redirect('home')

    return render(request, 'teacher_dashboard.html')


# =====================================================
# VIEW STUDENTS
# =====================================================

@login_required
def view_students(request):
    if not request.user.is_staff:
        return redirect('home')

    students = Student.objects.all()
    return render(request, 'view_students.html', {'students': students})


# =====================================================
# MARK ATTENDANCE
# =====================================================

@login_required
def mark_attendance(request):
    if not request.user.is_staff:
        return HttpResponse("❌ Only Teachers Allowed")

    students = Student.objects.all()

    if request.method == "POST":
        today = date.today()

        for student in students:
            status = request.POST.get(f"status_{student.id}")

            if not Attendance.objects.filter(student=student, date=today).exists():
                Attendance.objects.create(
                    student=student,
                    date=today,
                    status=status
                )

        return redirect('teacher_dashboard')

    return render(request, 'mark_attendance.html', {'students': students})


# =====================================================
# QR CODE
# =====================================================

def generate_qr(request):
    url = request.build_absolute_uri(reverse('home'))
    img = qrcode.make(url)

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return HttpResponse(buffer.getvalue(), content_type="image/png")


from datetime import date



from django.contrib.auth.decorators import login_required

@login_required
def update_leave_status(request, leave_id, action):
    if not request.user.is_staff:
        return redirect('home')

    leave = LeaveRequest.objects.get(id=leave_id)

    if action == "approve":
        leave.status = "Approved"
    elif action == "reject":
        leave.status = "Rejected"

    leave.save()

    return redirect("today_leaves")




def student_leaves(request):
    student_id = request.session.get("student_id")

    leaves = LeaveRequest.objects.filter(student_id=student_id)

    return render(request, "student_leaves.html", {"leaves": leaves})

@login_required
def today_leaves(request):
    if not request.user.is_staff:
        return redirect('home')

    today = date.today()

    leaves = LeaveRequest.objects.filter(
        from_date__lte=today,
        to_date__gte=today
    )

    return render(request, 'today_leaves.html', {'leaves': leaves})






 
from django.shortcuts import render, redirect
from .models import Student, Attendance

def hod_dashboard(request):
    
    if not request.user.is_authenticated or not request.user.is_superuser:
        return redirect("login_page")  # ✅ This URL exists
    

    students = Student.objects.all()

    search_query = request.GET.get("search", "")
    sort_order = request.GET.get("sort", "")
    selected_date = request.GET.get("date")

    student_data = []

    # 🔹 Overall student attendance %
    for student in students:
        total = Attendance.objects.filter(student=student).count()
        present = Attendance.objects.filter(student=student, status="Present").count()

        percentage = (present / total * 100) if total > 0 else 0

        student_data.append({
            "name": student.name,
            "roll_no": student.roll_no,
            "percentage": round(percentage, 2)
        })

    # 🔍 SEARCH
    if search_query:
        student_data = [
            s for s in student_data
            if search_query.lower() in s["name"].lower()
            or search_query.lower() in s["roll_no"].lower()
        ]

    # 📉 SORT
    if sort_order == "low":
        student_data = sorted(student_data, key=lambda x: x["percentage"])

    # 📊 Chart data
    names = [s["name"] for s in student_data]
    percentages = [s["percentage"] for s in student_data]

    # 📅 DAILY REPORT
    daily_records = []

    if selected_date:
        records = Attendance.objects.filter(date=selected_date)

        for record in records:
            daily_records.append({
                "name": record.student.name,
                "roll_no": record.student.roll_no,
                "status": record.status
            })

    return render(request, "hod_dashboard.html", {
        "students": student_data,
        "names": names,
        "percentages": percentages,
        "search_query": search_query,
        "selected_date": selected_date,
        "daily_records": daily_records
    })

def calculator(request):
    return render(request, 'calculator.html')



import csv
from django.shortcuts import render
from django.contrib import messages
from .models import Student, Attendance

def upload_attendance(request):
    if request.method == "POST":
        file = request.FILES.get('file')

        if not file:
            messages.error(request, "No file uploaded")
            return render(request, 'upload.html')

        try:
            decoded = file.read().decode('utf-8').splitlines()
            reader = csv.DictReader(decoded)

            count = 0

            for row in reader:
                roll_no = row.get('student_roll')
                date = row.get('date')
                status = row.get('status')

                try:
                    student = Student.objects.get(roll_no=roll_no)

                    # Prevent duplicate entry
                    if not Attendance.objects.filter(student=student, date=date).exists():
                        Attendance.objects.create(
                            student=student,
                            date=date,
                            status=status
                        )
                        count += 1

                except Student.DoesNotExist:
                    continue  # skip invalid students

            messages.success(request, f"{count} records uploaded successfully!")

        except Exception as e:
            messages.error(request, f"Error: {str(e)}")

    return render(request, 'upload.html')