# 🎓 College Attendance & Leave Management System

![Python](https://img.shields.io/badge/Python-3.11.9-blue?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-5.2.6-092E20?logo=django&logoColor=white)
![License](https://img.shields.io/badge/License-Not%20Specified-lightgrey)
![Status](https://img.shields.io/badge/Status-Active%20Development-brightgreen)

A full-featured **Django web application** for managing student attendance, leave requests, on-duty (OD) applications, assignments, grades, timetables, and departmental information for an academic institution. The system supports multiple user roles — **Student, Mentor/Teacher, Class Representative (CR), HOD (Head of Department), and Parent** — each with a dedicated dashboard and permission-scoped views.

---

## 📖 Table of Contents

- [Features](#-features)
- [Technology Stack](#-technology-stack)
- [Architecture & Workflow](#-architecture--workflow)
- [Installation](#-installation)
- [Usage](#-usage)
- [Project Structure](#-project-structure)
- [Screenshots](#-screenshots)
- [API & Application Endpoints](#-api--application-endpoints)
- [Dataset Information](#-dataset-information)
- [Model Information](#-model-information)
- [Future Improvements](#-future-improvements)
- [Contributing](#-contributing)
- [License](#-license)
- [Author](#-author)

---

## ✨ Features

### 👥 Role-Based Dashboards
- Separate dashboards and permissions for **Student**, **Mentor**, **Teacher**, **Class Representative**, **HOD**, and **Parent** accounts.
- Role-aware home/login redirection (`dashboard_redirect`) sending each user to the correct dashboard.

### 📝 Leave Management
- Students can submit leave requests (`apply_leave_api`) with from/to dates and a reason.
- Multi-level review workflow (Mentor / Superuser) with reviewer role, reviewer identity, and timestamp tracked on every request (`reviewed_by`, `reviewer_role`, `reviewed_at`).
- Approving a leave automatically generates corresponding `Attendance` records for the leave period.
- Leave status tracking page for students.

### 🗓️ Attendance
- Teachers can mark daily attendance per subject (`mark_attendance`), stored per student/subject/date (unique constraint prevents duplicates).
- Attendance percentage calculation using a configurable `ATTENDANCE_PENALTY` setting.
- Downloadable **PDF attendance reports** for HOD (via ReportLab).

### 🚩 Defaulter Tracking
- Bulk defaulter upload via Excel spreadsheets (pandas/openpyxl).
- Defaulter list view with per-student "action taken" tracking and updates.
- PDF export of the defaulter report.

### 🎟️ On-Duty (OD) Applications
- Students apply for OD against a specific **Event** (`apply_od`).
- Staff panel to **approve/reject** OD requests.
- OD status tracking page for students and parents.

### 📅 Events & Department Site
- Event creation, editing, and deletion with brochure file uploads.
- Departmental content models for **Staff profiles, Achievements, Award Winners, Photo Gallery, News Items, and Upcoming Events** (managed via Django Admin).

### 📚 Assignments & Grades
- CR/staff can create, edit, and delete assignments (with file attachments and due dates) per subject/batch.
- Students can view assignments relevant to their batch.
- Bulk grade upload via Excel (`GradeUpload` → generates `StudentGrade` rows), with per-student grade viewing.

### 🕒 Timetable
- Timetable creation per department/batch/subject/teacher with **room-clash validation** (prevents overlapping bookings in the same room/time slot).
- Timetable viewing for teachers/students.

### 🔔 Notifications
- Centralized in-app notification dispatcher (`send_notification`) tied to leave, OD, academic, and circular events.
- Unread notification polling, mark-as-read, mark-all-as-read, and delete endpoints.

### 👨‍👩‍👧 Parent Portal
- Parents (linked to a student via `ParentProfile`) get read-only access to their child's attendance, grades, leave history, defaulter status, OD status, and notifications.

### 🔐 Security & Auditing
- CSRF protection, `login_required` guards, and role checks on all mutating views.
- File upload validation (type/size/extension whitelist) on uploads.
- `select_for_update()` used on concurrent write operations.
- `ActivityLog` model for recording user actions with IP address.
- Production-ready security settings (`SECURE_SSL_REDIRECT`, `SECURE_HSTS_*`, `X_FRAME_OPTIONS`) auto-enabled when `DEBUG=False`.

### 🧮 Utilities
- Simple built-in calculator page.
- QR code generation helper (`qrcode` library) for building a shareable link to the homepage.

> **Note:** `requirements.txt` also lists a few packages (`celery`, `django-celery-beat`, `redis`, `twilio`, `mailjet-rest`, `scikit-learn`, `matplotlib`) that are **not currently wired into any view, task, or model** in the codebase. They appear to be reserved for planned features (e.g. async tasks, SMS/email alerts, analytics) rather than active functionality today.

---

## 🛠️ Technology Stack

| Layer | Technology |
|---|---|
| **Language** | Python 3.11.9 |
| **Framework** | Django 5.2.6 |
| **Database** | SQLite (default, local) / PostgreSQL (via `dj-database-url` + `psycopg2-binary`, production) |
| **Templating** | Django Template Language (server-rendered HTML) |
| **Frontend** | HTML, CSS, JavaScript (custom static assets + Owl Carousel / Font Awesome / animated.css) |
| **PDF Generation** | ReportLab |
| **Spreadsheet Handling** | pandas, openpyxl |
| **QR Codes** | qrcode |
| **Static Files** | WhiteNoise (`CompressedManifestStaticFilesStorage`) |
| **WSGI Server** | Gunicorn |
| **Configuration** | python-decouple (`.env`-based settings) |
| **Deployment Target** | Render (`.onrender.com` allowed host, `runtime.txt` pinned to Python 3.11.9) |

---

## 🏗️ Architecture & Workflow

The project follows Django's standard **Model–View–Template (MVT)** pattern and is split into four apps orchestrated by a central project package.

```
                          ┌─────────────────────┐
                          │      myproject       │
                          │  (settings / urls)   │
                          └──────────┬───────────┘
                                     │
        ┌───────────────┬───────────┼────────────────┬───────────────┐
        │               │           │                │
   ┌────▼────┐    ┌──────▼─────┐ ┌───▼───┐    ┌────────▼────────┐
   │leave_app│    │   events   │ │  od   │    │   department    │
   │ (core)  │    │(brochures, │ │(OD    │    │ (staff, gallery,│
   │         │◄───┤ event mgmt)│ │reqs)  │◄───┤ news, winners)  │
   └────┬────┘    └────────────┘ └───────┘    └─────────────────┘
        │
        ▼
  Students / Mentors / Teachers / CR / HOD / Parents
  (role-based dashboards, leave + attendance + grades + timetable)
```

**Typical request flow:**
1. A user logs in through `leave_app` (`login_page`), which authenticates against Django's built-in `User` model and redirects to a role-specific dashboard.
2. Students submit leave/OD requests → routed to Mentor/HOD/Staff for review.
3. On approval, `Attendance` records are generated automatically and a `Notification` is dispatched to relevant users.
4. Teachers mark attendance and manage assignments/grades per subject and batch.
5. HOD and staff export **PDF/Excel reports** for attendance and defaulters.
6. The `department` app powers the public-facing informational pages (staff directory, achievements, gallery, news) via Django Admin-managed content.

---

## ⚙️ Installation

### Prerequisites
- Python 3.11.9
- pip
- (Optional) PostgreSQL if not using the default SQLite database

### Steps

```bash
# 1. Clone the repository
git clone <your-repository-url>
cd attendance

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate      # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create a .env file in the project root (same folder as manage.py)
```

Create a `.env` file with the required environment variables:

```env
SECRET_KEY=your-django-secret-key
DEBUG=True
DATABASE_URL=sqlite:///db.sqlite3
```

> `DATABASE_URL` is optional — if omitted, the app falls back to a local `db.sqlite3` file automatically.

```bash
# 5. Apply database migrations
python manage.py migrate

# 6. Create an admin/superuser account
python manage.py createsuperuser

# 7. Collect static files (required for WhiteNoise in production)
python manage.py collectstatic

# 8. Run the development server
python manage.py runserver
```

The application will be available at `http://127.0.0.1:8000/`.

---

## 🚀 Usage

- **Home / Login:** Visit `/` to reach the landing page, then log in at `/login/`.
- **Students:** After login, land on `/student/dashboard/` to view attendance, apply for leave, check assignments, view grades, and check defaulter status.
- **Mentors/Teachers:** Access `/mentor/dashboard/` or `/teacher/dashboard/` to review leave requests, mark attendance, and manage timetables.
- **Class Representatives:** Use `/cr/dashboard/` to manage assignments for their batch.
- **HOD:** Use `/hod/dashboard/` to review escalated leaves, download attendance/defaulter PDF reports, and manage timetables department-wide.
- **Parents:** Log in separately at `/parent/login/` to view `/parent/dashboard/` for a read-only summary of their child's academic activity.
- **OD Requests:** Students apply for On-Duty via `/od/apply-od/<event_id>/`; staff review them at `/od/staff/`.
- **Events:** Manage college events and brochures via `/events/`.
- **Django Admin:** Manage department content (Staff, Gallery, News, Achievements, Winners) at `/admin/`.

---

## 📁 Project Structure

```
attendance/
├── manage.py
├── requirements.txt
├── runtime.txt
├── db.sqlite3
│
├── myproject/                 # Project settings & root URL configuration
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py / asgi.py
│   └── templates/              # Legacy/duplicate template set
│
├── leave_app/                  # Core application (auth, leave, attendance, grades, etc.)
│   ├── models.py                # Department, Subject, Student, LeaveRequest, Attendance,
│   │                             # Timetable, Assignment, Notification, DefaulterStudent,
│   │                             # ActivityLog, ParentProfile, GradeUpload, StudentGrade
│   ├── views.py                  # All role dashboards, leave/attendance/OD/grade logic
│   ├── urls.py
│   ├── utils.py                   # send_notification() helper
│   ├── decorators.py
│   ├── forms.py
│   ├── serializers.py
│   └── management/commands/
│
├── events/                      # Event & brochure management
│   ├── models.py                 # Event
│   ├── views.py / urls.py
│
├── od/                           # On-Duty application workflow
│   ├── models.py                 # ODApplication
│   ├── views.py / urls.py
│
├── department/                  # Departmental informational content
│   ├── models.py                 # Staff, Achievement, Winner, Gallery, NewsItem, UpcomingEvent
│   ├── views.py / urls.py
│
├── templates/                    # HTML templates (dashboards, forms, reports)
├── static/                       # CSS, JS, and static assets
├── staticfiles/                  # Collected static files (WhiteNoise output)
└── media/                        # Uploaded files (brochures, assignments, grades, staff photos)
```

---

## 🖼️ Screenshots

> Screenshots are not included in this repository. Add images to a `docs/screenshots/` folder and update the paths below.

| Login Page | Student Dashboard | HOD Dashboard |
|---|---|---|
| ![Login Page](docs/screenshots/login.png) | ![Student Dashboard](docs/screenshots/student_dashboard.png) | ![HOD Dashboard](docs/screenshots/hod_dashboard.png) |

| Attendance Marking | Leave Review | Defaulter Report (PDF) |
|---|---|---|
| ![Attendance](docs/screenshots/mark_attendance.png) | ![Leave Review](docs/screenshots/leave_status.png) | ![Defaulter PDF](docs/screenshots/defaulter_report.png) |

---

## 🔌 API & Application Endpoints

This project is primarily a **server-rendered Django application** (HTML views), with a small number of **JSON/AJAX endpoints** used by front-end scripts. There is no separate REST framework (e.g. DRF) in use.

### JSON / AJAX Endpoints

| Method | Endpoint | View | Description |
|---|---|---|---|
| POST | `/api/apply-leave/` | `apply_leave_api` | Submit a new leave request as JSON |
| GET | `/notifications/unread/` | `get_notifications` | Fetch unread notifications for the logged-in user |
| POST | `/notifications/read/<id>/` | `mark_as_read` | Mark a single notification as read |
| POST | `/notifications/read-all/` | `mark_all_notifications_read` | Mark all notifications as read |
| POST | `/notifications/delete/<id>/` | `delete_notification` | Delete a notification |
| POST | `/defaulters/update-action/<id>/` | `update_action` | Update the disciplinary action for a defaulter |

### Key HTML/Report Routes

| Method | Endpoint | Description |
|---|---|---|
| GET/POST | `/login/`, `/logout/`, `/parent/login/` | Authentication |
| GET | `/student/dashboard/`, `/mentor/dashboard/`, `/teacher/dashboard/`, `/hod/dashboard/`, `/cr/dashboard/`, `/parent/dashboard/` | Role dashboards |
| GET/POST | `/student/apply/` | Student leave application form |
| GET/POST | `/leave/review/<id>/<action>/` | Mentor/HOD leave approval or rejection |
| GET/POST | `/teacher/mark-attendance/` | Attendance marking |
| GET | `/hod/attendance-report-pdf/`, `/hod/defaulter-report-pdf/` | Downloadable PDF reports |
| GET/POST | `/upload/defaulters/`, `/upload/grades/` | Bulk Excel uploads |
| GET/POST | `/assignments/create/`, `/assignments/edit/<id>/`, `/assignments/delete/<id>/` | Assignment management |
| GET/POST | `/timetable/create/` | Timetable creation |
| GET/POST | `/od/apply-od/<event_id>/`, `/od/approve/<id>/`, `/od/reject/<id>/` | On-Duty workflow |
| GET/POST | `/events/create/`, `/events/edit/<id>/`, `/events/delete/<id>/` | Event management |

---

## 🗃️ Dataset Information

The application does not ship with a fixed external dataset. All data (students, staff, attendance, leave requests, grades, events, etc.) is created and stored through the application itself in the configured database (SQLite by default). Bulk data can be imported by administrators/staff through:
- **Defaulter uploads** — Excel spreadsheets parsed with `pandas`/`openpyxl` (`upload_defaulters`).
- **Grade uploads** — Excel spreadsheets parsed and converted into `StudentGrade` records (`upload_grades`).

Sample/reference spreadsheet files are present in the repository under `media/grades/` and `sample.xlsx`, used during development/testing of the upload features.

---

## 🧠 Model Information

There is **no machine learning model** in this project. "Model" in this context refers to **Django ORM data models**, defined across the four apps:

| App | Models |
|---|---|
| `leave_app` | `Department`, `Subject`, `Student`, `LeaveRequest`, `Attendance`, `Timetable`, `Assignment`, `Notification`, `DefaulterStudent`, `ActivityLog`, `ParentProfile`, `GradeUpload`, `StudentGrade` |
| `events` | `Event` |
| `od` | `ODApplication` |
| `department` | `Staff`, `Achievement`, `Winner`, `Gallery`, `NewsItem`, `UpcomingEvent` |

Authentication relies on Django's built-in `django.contrib.auth.models.User`, with `Student` and `ParentProfile` extending it via one-to-one relations.

---

## 🔮 Future Improvements

Based on unused dependencies already present in `requirements.txt`, natural next steps for this project include:
- Integrating **Celery + django-celery-beat + Redis** for background/scheduled tasks (e.g. automated leave reminders, defaulter recalculation).
- Wiring up **Twilio** and/or **Mailjet** for SMS/email notifications to students and parents.
- Adding **analytics/insights** using the already-installed `pandas`, `scikit-learn`, and `matplotlib` (e.g. attendance trend prediction, at-risk student flagging).
- Exposing a proper **REST API** (e.g. via Django REST Framework) for a future mobile app or SPA frontend.
- Adding automated tests (current `tests.py` files in each app are placeholders).
- Removing duplicate/legacy template directories (`myproject/templates/` vs root `templates/`) for maintainability.

---

## 🤝 Contributing

Contributions are welcome. To contribute:

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/your-feature-name`.
3. Commit your changes: `git commit -m "Add your feature"`.
4. Push to your branch: `git push origin feature/your-feature-name`.
5. Open a Pull Request describing your changes.

Please avoid committing sensitive files such as `.env`, `db.sqlite3`, and media uploads.

---

## 📄 License

No license file is currently included in this repository. Until one is added, all rights are reserved by the author. Consider adding an [MIT](https://choosealicense.com/licenses/mit/) or other open-source license if you intend to share or accept contributions to this project.

---

## 👤 Author

**Project maintained by the repository owner.**
Feel free to update this section with your name, GitHub profile, and contact information.
