from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from functools import wraps
from markupsafe import Markup
import os
import json
import hashlib

app = Flask(__name__)

# Add nl2br filter
@app.template_filter('nl2br')
def nl2br(value):
    if value:
        return Markup(value.replace('\n', '<br>'))
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///employees.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Please log in to access this page', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Please log in to access this page', 'warning')
            return redirect(url_for('login'))
        if not session.get('is_admin', False):
            flash('You do not have permission to access this page', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# User model for authentication
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship with Employee
    employee = db.relationship('Employee', backref=db.backref('user', lazy=True, uselist=False), foreign_keys=[employee_id])
    
    def __repr__(self):
        return f'<User {self.username}>'
    
    def set_password(self, password):
        self.password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    def check_password(self, password):
        return self.password_hash == hashlib.sha256(password.encode()).hexdigest()

# Education model
class Education(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    institution = db.Column(db.String(100), nullable=False)
    degree = db.Column(db.String(100), nullable=False)
    field_of_study = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Education {self.degree} from {self.institution}>'

# Certification model
class Certification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    issuing_organization = db.Column(db.String(100), nullable=False)
    issue_date = db.Column(db.Date, nullable=False)
    expiry_date = db.Column(db.Date, nullable=True)
    credential_id = db.Column(db.String(100), nullable=True)
    credential_url = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Certification {self.name} from {self.issuing_organization}>'

# Employee model - updated with new fields
class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.String(50), unique=True, nullable=True)  # Added employee ID field
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    department = db.Column(db.String(50), nullable=False)
    position = db.Column(db.String(50), nullable=False)
    hire_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    current_address = db.Column(db.String(200), nullable=False)  # Renamed from address
    permanent_address = db.Column(db.String(200), nullable=True)  # Added permanent address
    salary = db.Column(db.Float, default=0)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    educations = db.relationship('Education', backref='employee', lazy=True, cascade="all, delete-orphan")
    certifications = db.relationship('Certification', backref='employee', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Employee {self.first_name} {self.last_name}>'

# Create database tables and default admin user
with app.app_context():
    db.create_all()
    
    # Create default admin user if it doesn't exist
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(username='admin', is_admin=True)
        admin.set_password('admin')
        db.session.add(admin)
        db.session.commit()
        print("Default admin user created")

@app.route('/login', methods=['GET', 'POST'])
def login():
    # If user is already logged in, redirect to index
    if 'logged_in' in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            session['logged_in'] = True
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            session['user_id'] = user.id
            flash(f'Welcome back, {username}!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    session.pop('is_admin', None)
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    # Check if user is admin
    if session.get('is_admin', False):
        # Admin dashboard
        # Get all unique departments
        departments = db.session.query(Employee.department).distinct().all()
        departments = [dept[0] for dept in departments]
        
        # Count employees per department and total
        department_counts = {}
        total_employees = 0
        
        for dept in departments:
            count = Employee.query.filter_by(department=dept).count()
            department_counts[dept] = count
            total_employees += count
        
        return render_template('index.html', 
                              departments=departments, 
                              department_counts=department_counts,
                              total_employees=total_employees)
    else:
        # Employee dashboard
        # Get the current user
        user = User.query.filter_by(username=session.get('username')).first()
        
        # Check if user has an employee profile
        if user and user.employee_id:
            employee = Employee.query.get(user.employee_id)
            if employee:
                educations = Education.query.filter_by(employee_id=employee.id).all()
                certifications = Certification.query.filter_by(employee_id=employee.id).all()
                return render_template('employee_dashboard.html', employee=employee, educations=educations, certifications=certifications)
        
        # Redirect to self-onboarding if no profile exists
        flash('Please complete your profile information', 'info')
        return redirect(url_for('self_onboarding'))

@app.route('/department/<department>')
@login_required
def department_employees(department):
    employees = Employee.query.filter_by(department=department).all()
    return render_template('department_employees.html', department=department, employees=employees)

@app.route('/add-department', methods=['GET', 'POST'])
@admin_required
def add_department():
    if request.method == 'POST':
        department_name = request.form.get('department_name')
        
        if not department_name:
            flash('Department name cannot be empty', 'danger')
            return redirect(url_for('add_department'))
        
        # Check if department already exists
        existing_departments = db.session.query(Employee.department).distinct().all()
        existing_departments = [dept[0] for dept in existing_departments if dept[0]]
        
        if department_name in existing_departments:
            flash(f'Department "{department_name}" already exists', 'warning')
            return redirect(url_for('index'))
        
        # Create a placeholder employee to establish the department
        placeholder = Employee(
            first_name="Department",
            last_name="Placeholder",
            email=f"{department_name.lower().replace(' ', '.')}@example.com",
            phone="N/A",
            department=department_name,
            position="Department Head",
            hire_date=datetime.utcnow(),
            salary=0,
            current_address="N/A",
            permanent_address="N/A",
            notes="This is a placeholder record to establish the department. You can delete this record after adding real employees to this department."
        )
        
        db.session.add(placeholder)
        db.session.commit()
        
        flash(f'Department "{department_name}" has been added successfully', 'success')
        return redirect(url_for('index'))
    
    return render_template('add_department.html')

@app.route('/search')
@login_required
def search_employees():
    query = request.args.get('query', '')
    if not query:
        return redirect(url_for('index'))
    
    # Search by name or position
    employees = Employee.query.filter(
        db.or_(
            Employee.first_name.ilike(f'%{query}%'),
            Employee.last_name.ilike(f'%{query}%'),
            Employee.position.ilike(f'%{query}%')
        )
    ).all()
    
    return render_template('search_results.html', employees=employees, query=query)

@app.route('/positions')
@login_required
def get_positions():
    query = request.args.get('q', '')
    positions = db.session.query(Employee.position).distinct().filter(
        Employee.position.ilike(f'%{query}%')
    ).all()
    return jsonify([position[0] for position in positions])

@app.route('/add', methods=['GET', 'POST'])
@admin_required
def add_employee():
    # Get all unique departments for the dropdown
    departments = db.session.query(Employee.department).distinct().all()
    departments = [dept[0] for dept in departments]
    
    # Add default departments if none exist
    if not departments:
        departments = [
            "Human Resources", "Information Technology", "Finance", 
            "Marketing", "Operations", "Sales", 
            "Research & Development", "Customer Support"
        ]
    
    if request.method == 'POST':
        employee_id = request.form.get('employee_id', '')
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        phone = request.form['phone']
        department = request.form['department']
        position = request.form['position']
        hire_date_str = request.form['hire_date']
        current_address = request.form['current_address']
        permanent_address = request.form.get('permanent_address', '')
        salary = request.form.get('salary', 0)
        notes = request.form.get('notes', '')
        
        # Convert string date to datetime object
        hire_date = datetime.strptime(hire_date_str, '%Y-%m-%d').date()
        
        # Convert salary to float if provided
        try:
            salary = float(salary) if salary else 0
        except ValueError:
            salary = 0
        
        # Check if email already exists
        existing_employee = Employee.query.filter_by(email=email).first()
        if existing_employee:
            flash('Email already exists!', 'danger')
            return redirect(url_for('add_employee'))
        
        # Check if employee_id already exists (if provided)
        if employee_id:
            existing_employee_id = Employee.query.filter_by(employee_id=employee_id).first()
            if existing_employee_id:
                flash('Employee ID already exists!', 'danger')
                return redirect(url_for('add_employee'))
        
        # Create new employee
        new_employee = Employee(
            employee_id=employee_id,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            department=department,
            position=position,
            hire_date=hire_date,
            current_address=current_address,
            permanent_address=permanent_address,
            salary=salary,
            notes=notes
        )
        
        # Add to database
        db.session.add(new_employee)
        db.session.commit()
        
        # Process education information if provided
        education_count = int(request.form.get('education_count', 0))
        for i in range(education_count):
            if request.form.get(f'institution_{i}'):
                institution = request.form.get(f'institution_{i}')
                degree = request.form.get(f'degree_{i}')
                field_of_study = request.form.get(f'field_of_study_{i}')
                start_date_str = request.form.get(f'edu_start_date_{i}')
                end_date_str = request.form.get(f'edu_end_date_{i}')
                description = request.form.get(f'edu_description_{i}', '')
                
                # Convert string dates to datetime objects
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else None
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None
                
                education = Education(
                    employee_id=new_employee.id,
                    institution=institution,
                    degree=degree,
                    field_of_study=field_of_study,
                    start_date=start_date,
                    end_date=end_date,
                    description=description
                )
                db.session.add(education)
        
        # Process certification information if provided
        cert_count = int(request.form.get('certification_count', 0))
        for i in range(cert_count):
            if request.form.get(f'cert_name_{i}'):
                name = request.form.get(f'cert_name_{i}')
                issuing_organization = request.form.get(f'issuing_organization_{i}')
                issue_date_str = request.form.get(f'issue_date_{i}')
                expiry_date_str = request.form.get(f'expiry_date_{i}')
                credential_id = request.form.get(f'credential_id_{i}', '')
                credential_url = request.form.get(f'credential_url_{i}', '')
                
                # Convert string dates to datetime objects
                issue_date = datetime.strptime(issue_date_str, '%Y-%m-%d').date() if issue_date_str else None
                expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d').date() if expiry_date_str else None
                
                certification = Certification(
                    employee_id=new_employee.id,
                    name=name,
                    issuing_organization=issuing_organization,
                    issue_date=issue_date,
                    expiry_date=expiry_date,
                    credential_id=credential_id,
                    credential_url=credential_url
                )
                db.session.add(certification)
        
        db.session.commit()
        
        flash('Employee added successfully!', 'success')
        return redirect(url_for('index'))
    
    return render_template('add_employee.html', departments=departments)

@app.route('/employee/<int:id>')
@login_required
def employee_details(id):
    employee = Employee.query.get_or_404(id)
    educations = Education.query.filter_by(employee_id=id).all()
    certifications = Certification.query.filter_by(employee_id=id).all()
    return render_template('employee_details.html', employee=employee, educations=educations, certifications=certifications)

@app.route('/employee/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_employee(id):
    employee = Employee.query.get_or_404(id)
    
    # Get all unique departments for the dropdown
    departments = db.session.query(Employee.department).distinct().all()
    departments = [dept[0] for dept in departments]
    
    if request.method == 'POST':
        # Check if employee_id is being changed and if it already exists
        new_employee_id = request.form.get('employee_id', '')
        if new_employee_id and new_employee_id != employee.employee_id:
            existing_employee_id = Employee.query.filter_by(employee_id=new_employee_id).first()
            if existing_employee_id:
                flash('Employee ID already exists!', 'danger')
                return redirect(url_for('edit_employee', id=employee.id))
        
        employee.employee_id = new_employee_id
        employee.first_name = request.form['first_name']
        employee.last_name = request.form['last_name']
        employee.email = request.form['email']
        employee.phone = request.form['phone']
        employee.department = request.form['department']
        employee.position = request.form['position']
        employee.hire_date = datetime.strptime(request.form['hire_date'], '%Y-%m-%d').date()
        employee.current_address = request.form['current_address']
        employee.permanent_address = request.form.get('permanent_address', '')
        
        # Get salary and notes
        salary = request.form.get('salary', 0)
        employee.notes = request.form.get('notes', '')
        
        # Convert salary to float if provided
        try:
            employee.salary = float(salary) if salary else 0
        except ValueError:
            employee.salary = 0
        
        # Update education information
        # First, remove all existing education records for this employee
        Education.query.filter_by(employee_id=employee.id).delete()
        
        # Then add the new education records
        education_count = int(request.form.get('education_count', 0))
        for i in range(education_count):
            if request.form.get(f'institution_{i}'):
                institution = request.form.get(f'institution_{i}')
                degree = request.form.get(f'degree_{i}')
                field_of_study = request.form.get(f'field_of_study_{i}')
                start_date_str = request.form.get(f'edu_start_date_{i}')
                end_date_str = request.form.get(f'edu_end_date_{i}')
                description = request.form.get(f'edu_description_{i}', '')
                
                # Convert string dates to datetime objects
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else None
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None
                
                education = Education(
                    employee_id=employee.id,
                    institution=institution,
                    degree=degree,
                    field_of_study=field_of_study,
                    start_date=start_date,
                    end_date=end_date,
                    description=description
                )
                db.session.add(education)
        
        # Update certification information
        # First, remove all existing certification records for this employee
        Certification.query.filter_by(employee_id=employee.id).delete()
        
        # Then add the new certification records
        cert_count = int(request.form.get('certification_count', 0))
        for i in range(cert_count):
            if request.form.get(f'cert_name_{i}'):
                name = request.form.get(f'cert_name_{i}')
                issuing_organization = request.form.get(f'issuing_organization_{i}')
                issue_date_str = request.form.get(f'issue_date_{i}')
                expiry_date_str = request.form.get(f'expiry_date_{i}')
                credential_id = request.form.get(f'credential_id_{i}', '')
                credential_url = request.form.get(f'credential_url_{i}', '')
                
                # Convert string dates to datetime objects
                issue_date = datetime.strptime(issue_date_str, '%Y-%m-%d').date() if issue_date_str else None
                expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d').date() if expiry_date_str else None
                
                certification = Certification(
                    employee_id=employee.id,
                    name=name,
                    issuing_organization=issuing_organization,
                    issue_date=issue_date,
                    expiry_date=expiry_date,
                    credential_id=credential_id,
                    credential_url=credential_url
                )
                db.session.add(certification)
        
        db.session.commit()
        flash('Employee updated successfully!', 'success')
        return redirect(url_for('employee_details', id=employee.id))
    
    educations = Education.query.filter_by(employee_id=id).all()
    certifications = Certification.query.filter_by(employee_id=id).all()
    return render_template('edit_employee.html', employee=employee, departments=departments, educations=educations, certifications=certifications)

@app.route('/employee/<int:id>/delete', methods=['POST'])
@admin_required
def delete_employee(id):
    employee = Employee.query.get_or_404(id)
    db.session.delete(employee)
    db.session.commit()
    flash('Employee deleted successfully!', 'success')
    return redirect(url_for('index'))

@app.route('/all-employees')
@login_required
def all_employees():
    employees = Employee.query.all()
    return render_template('all_employees.html', employees=employees)

@app.route('/self-onboarding', methods=['GET', 'POST'])
@login_required
def self_onboarding():
    # Check if user is an employee (not admin)
    if session.get('is_admin', False):
        flash('This page is for employees only', 'warning')
        return redirect(url_for('index'))
    
    # Get the current user
    user = User.query.filter_by(username=session.get('username')).first()
    
    if not user:
        flash('User not found. Please log in again.', 'danger')
        return redirect(url_for('logout'))
    
    # Check if user already has an employee profile
    if user.employee_id:
        employee = Employee.query.get(user.employee_id)
        educations = Education.query.filter_by(employee_id=employee.id).all()
        certifications = Certification.query.filter_by(employee_id=employee.id).all()
        
        # Get all unique departments for the dropdown
        departments = db.session.query(Employee.department).distinct().all()
        departments = [dept[0] for dept in departments]
        
        if request.method == 'POST':
            # Update employee information
            employee.employee_id = request.form.get('employee_id', '')
            employee.first_name = request.form['first_name']
            employee.last_name = request.form['last_name']
            employee.email = request.form['email']
            employee.phone = request.form['phone']
            employee.current_address = request.form['current_address']
            employee.permanent_address = request.form.get('permanent_address', '')
            
            # Update education information
            # First, remove all existing education records for this employee
            Education.query.filter_by(employee_id=employee.id).delete()
            
            # Then add the new education records
            education_count = int(request.form.get('education_count', 0))
            for i in range(education_count):
                if request.form.get(f'institution_{i}'):
                    institution = request.form.get(f'institution_{i}')
                    degree = request.form.get(f'degree_{i}')
                    field_of_study = request.form.get(f'field_of_study_{i}')
                    start_date_str = request.form.get(f'edu_start_date_{i}')
                    end_date_str = request.form.get(f'edu_end_date_{i}')
                    description = request.form.get(f'edu_description_{i}', '')
                    
                    # Convert string dates to datetime objects
                    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else None
                    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None
                    
                    education = Education(
                        employee_id=employee.id,
                        institution=institution,
                        degree=degree,
                        field_of_study=field_of_study,
                        start_date=start_date,
                        end_date=end_date,
                        description=description
                    )
                    db.session.add(education)
            
            # Update certification information
            # First, remove all existing certification records for this employee
            Certification.query.filter_by(employee_id=employee.id).delete()
            
            # Then add the new certification records
            cert_count = int(request.form.get('certification_count', 0))
            for i in range(cert_count):
                if request.form.get(f'cert_name_{i}'):
                    name = request.form.get(f'cert_name_{i}')
                    issuing_organization = request.form.get(f'issuing_organization_{i}')
                    issue_date_str = request.form.get(f'issue_date_{i}')
                    expiry_date_str = request.form.get(f'expiry_date_{i}')
                    credential_id = request.form.get(f'credential_id_{i}', '')
                    credential_url = request.form.get(f'credential_url_{i}', '')
                    
                    # Convert string dates to datetime objects
                    issue_date = datetime.strptime(issue_date_str, '%Y-%m-%d').date() if issue_date_str else None
                    expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d').date() if expiry_date_str else None
                    
                    certification = Certification(
                        employee_id=employee.id,
                        name=name,
                        issuing_organization=issuing_organization,
                        issue_date=issue_date,
                        expiry_date=expiry_date,
                        credential_id=credential_id,
                        credential_url=credential_url
                    )
                    db.session.add(certification)
            
            db.session.commit()
            flash('Your profile has been updated successfully!', 'success')
            return redirect(url_for('self_onboarding'))
        
        return render_template('self_onboarding.html', employee=employee, departments=departments, educations=educations, certifications=certifications)
    else:
        # User doesn't have an employee profile yet, create a basic one
        if request.method == 'POST':
            # Create new employee
            new_employee = Employee(
                employee_id=request.form.get('employee_id', ''),
                first_name=request.form['first_name'],
                last_name=request.form['last_name'],
                email=request.form['email'],
                phone=request.form['phone'],
                department=request.form.get('department', 'Unassigned'),
                position=request.form.get('position', 'New Hire'),
                hire_date=datetime.utcnow().date(),
                current_address=request.form['current_address'],
                permanent_address=request.form.get('permanent_address', ''),
                salary=0,  # Salary will be set by admin
                notes=''
            )
            
            # Add to database
            db.session.add(new_employee)
            db.session.commit()
            
            # Link employee to user
            user.employee_id = new_employee.id
            db.session.commit()
            
            # Process education information if provided
            education_count = int(request.form.get('education_count', 0))
            for i in range(education_count):
                if request.form.get(f'institution_{i}'):
                    institution = request.form.get(f'institution_{i}')
                    degree = request.form.get(f'degree_{i}')
                    field_of_study = request.form.get(f'field_of_study_{i}')
                    start_date_str = request.form.get(f'edu_start_date_{i}')
                    end_date_str = request.form.get(f'edu_end_date_{i}')
                    description = request.form.get(f'edu_description_{i}', '')
                    
                    # Convert string dates to datetime objects
                    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else None
                    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None
                    
                    education = Education(
                        employee_id=new_employee.id,
                        institution=institution,
                        degree=degree,
                        field_of_study=field_of_study,
                        start_date=start_date,
                        end_date=end_date,
                        description=description
                    )
                    db.session.add(education)
            
            # Process certification information if provided
            cert_count = int(request.form.get('certification_count', 0))
            for i in range(cert_count):
                if request.form.get(f'cert_name_{i}'):
                    name = request.form.get(f'cert_name_{i}')
                    issuing_organization = request.form.get(f'issuing_organization_{i}')
                    issue_date_str = request.form.get(f'issue_date_{i}')
                    expiry_date_str = request.form.get(f'expiry_date_{i}')
                    credential_id = request.form.get(f'credential_id_{i}', '')
                    credential_url = request.form.get(f'credential_url_{i}', '')
                    
                    # Convert string dates to datetime objects
                    issue_date = datetime.strptime(issue_date_str, '%Y-%m-%d').date() if issue_date_str else None
                    expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d').date() if expiry_date_str else None
                    
                    certification = Certification(
                        employee_id=new_employee.id,
                        name=name,
                        issuing_organization=issuing_organization,
                        issue_date=issue_date,
                        expiry_date=expiry_date,
                        credential_id=credential_id,
                        credential_url=credential_url
                    )
                    db.session.add(certification)
            
            db.session.commit()
            
            flash('Your profile has been created successfully!', 'success')
            return redirect(url_for('self_onboarding'))
        
        # Get all unique departments for the dropdown
        departments = db.session.query(Employee.department).distinct().all()
        departments = [dept[0] for dept in departments]
        
        return render_template('self_onboarding.html', employee=None, departments=departments, educations=[], certifications=[])

@app.route('/register', methods=['GET', 'POST'])
def register():
    # If user is already logged in, redirect to index
    if 'logged_in' in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        # Check if passwords match
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('register'))
        
        # Check if username already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists', 'danger')
            return redirect(url_for('register'))
        
        # Create new user
        new_user = User(username=username, is_admin=False)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=12000, debug=True)