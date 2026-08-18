# Student Compass

A Django web app for academic management — track courses, assignments,
grades, and GPA across semesters, all in one place.

**Stack:** Django, SQLite/PostgreSQL, HTML/CSS (custom ivory/burgundy design
system with Fraunces, Inter, and IBM Plex Mono typography)

---

## Features

- **Dashboard** — greeting, progress, deadline countdowns, GPA prediction
- **Courses** — per-course pages with teacher, office, schedule, materials
- **Assignments** — track title, due date, difficulty, progress, priority
- **Grades / GPA calculator** — enter midterm/final scores, auto-calculates
  current grade and what you need on the final
- **Study track (calendar)** — semester-wide view of assignments

---

## Setup

1. Clone the repo
   ```bash
   git clone https://github.com/Kamola618/student_compass.git
   cd student_compass
   ```

2. Create a virtual environment
   ```bash
   python -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   ```

3. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

4. Run migrations
   ```bash
   python manage.py migrate
   ```

5. Create a superuser
   ```bash
   python manage.py createsuperuser
   ```

6. Run the dev server
   ```bash
   python manage.py runserver
   ```

---

## Project Structure

```
student-compass/
├── courses/        # Course, Semester models & views
├── assignments/     # Assignment model, forms, views
├── grades/          # Grade model, GradeForm, grade calculations
├── templates/        # HTML templates
├── static/           # CSS (design system), JS, per-course colors
```
