# Teacher Section Assignment Feature Guide

## Overview
Teachers can now assign themselves to manage multiple student sections. This feature allows teachers to indicate which sections they're responsible for overseeing.

## Changes Made

### 1. Database Model Changes
**File:** `Accounting_System_app/models.py`

- Added a `ManyToManyField` to the `StudentSection` model:
  ```python
  teachers = models.ManyToManyField(User, related_name='managed_sections', blank=True)
  ```
  - This allows multiple teachers to manage a section
  - Allows a teacher to manage multiple sections
  - Related name `managed_sections` allows accessing all sections a teacher manages via `teacher_user.managed_sections.all()`

### 2. Database Migration
**File:** `Accounting_System_app/migrations/0031_studentsection_teachers.py`

- Created migration to add the `teachers` field to the `student_sections` table
- Run with: `python manage.py migrate`

### 3. Backend View
**File:** `Accounting_System_app/views.py`

Added new view function:
```python
@role_required(['teacher'])
@require_http_methods(["POST"])
def assign_teacher_to_sections(request):
```

**Features:**
- Teachers POST their selected section IDs via form
- Removes teacher from all sections first, then adds to selected ones
- Shows success messages indicating how many sections they're now managing
- Redirects back to teacher dashboard

### 4. URL Route
**File:** `Accounting_System_app/urls.py`

Added URL pattern:
```python
path('teacher/sections/assign-self/', views.assign_teacher_to_sections, name='assign_teacher_to_sections'),
```

### 5. Teacher Dashboard View
**File:** `Accounting_System_app/views.py`

Updated `teacher_dashboard()` view to include:
```python
teacher_managed_sections = request.user.managed_sections.all()
```

Added to template context for display.

### 6. User Interface
**File:** `Accounting_System_app/templates/Front_End/teacher_dashboard.html`

Added new section titled **"Teacher Section Assignment"** with:

**Features:**
- Lists all available sections with:
  - Section name
  - Number of students in the section
  - Number of assigned account groups
- Checkboxes to select/deselect sections
- Visual feedback showing current number of managed sections
- Submit button to save assignments

**Styling:**
- Card-based layout with Bootstrap styling
- Color-coded information cards
- Clear visual hierarchy
- Responsive design

## How to Use

### As a Teacher:

1. **Log in** to your teacher account
2. **Go to Dashboard** - `Teacher > Home` or `/dashboard/teacher/`
3. **Scroll to "Teacher Section Assignment"** section
4. **Select Sections** - Check the boxes for sections you manage
5. **Click "Save Section Assignments"** button
6. **Confirmation** - You'll see a success message indicating how many sections you're managing

### Managing Multiple Sections:
- A teacher can manage as many sections as needed
- Simply check multiple section boxes and save
- Visit the dashboard anytime to updated your managed sections

## Technical Details

### Database Schema
```
StudentSection (student_sections table)
├── id (PK)
├── name
├── created_at
├── account_groups (M2M)
└── teachers (M2M) ← NEW FIELD
    └── Links to auth_user table
    └── Via studentsection_teachers junction table
```

### Related Queries

**Get all sections a teacher manages:**
```python
teacher.managed_sections.all()
```

**Get all teachers managing a section:**
```python
section.teachers.all()
```

**Add teacher to section:**
```python
section.teachers.add(teacher_user)
```

**Remove teacher from section:**
```python
section.teachers.remove(teacher_user)
```

## Future Enhancements

Possible improvements to this feature:

1. **Admin Dashboard** - Show admin all teacher assignments
2. **Teacher Reports** - Show teachers reports for their managed sections only
3. **Notifications** - Notify teachers when new students are added to their sections
4. **Permissions** - Limit teacher actions based on their managed sections
5. **Bulk Assignment** - Admin can assign teachers to multiple sections at once
6. **Remove from Section** - Individual removal buttons per section
7. **Section Details** - Show more info (students list, account groups) in the assignment UI

## Testing

To test the feature:

1. Create multiple student sections
2. Log in as a teacher
3. Assign yourself to 1-3 sections
4. Verify checkboxes are checked on page reload
5. Unassign from some sections
6. Verify changes persist

## Troubleshooting

**Checkboxes not checking:**
- Clear browser cache
- Reload the page after saving
- Check that form is submitting correctly

**Assigned sections not showing:**
- Verify migration was applied: `python manage.py showmigrations`
- Check database directly in Django admin

**Migration errors:**
- Ensure you're in the correct directory: `Accounting System v.03/Accounting_Systemv0.2`
- Run: `python manage.py migrate --verbosity 2` for detailed output

## Files Modified

1. ✅ `Accounting_System_app/models.py` - Added teachers field
2. ✅ `Accounting_System_app/migrations/0031_studentsection_teachers.py` - New migration
3. ✅ `Accounting_System_app/views.py` - Added view function & updated dashboard
4. ✅ `Accounting_System_app/urls.py` - Added URL route
5. ✅ `Accounting_System_app/templates/Front_End/teacher_dashboard.html` - Added UI

