#!/usr/bin/env python3
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import boto3
from itsdangerous.url_safe import URLSafeTimedSerializer as Serializer
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///task_tracker.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['AWS_REGION_NAME'] = 'your-aws-region'
app.config['AWS_ACCESS_KEY_ID'] = 'your-aws-access-key-id'
app.config['AWS_SECRET_ACCESS_KEY'] = 'your-aws-secret-access-key'
app.config['SES_EMAIL_SOURCE'] = 'your-ses-verified-email-address'

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

project_shares = db.Table('project_shares',
    db.Column('project_id', db.Integer, db.ForeignKey('project.id')),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'))
)

# =============================
# MODELS
# =============================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    
    projects = db.relationship('Project', backref='owner', lazy=True)
    tasks = db.relationship('Task', backref='assignee', lazy=True)
    shared_projects = db.relationship('Project', secondary=project_shares, backref=db.backref('shared_with_users', lazy='dynamic'))
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
        
    def check_password(self, password):
         return check_password_hash(self.password_hash, password)

    def get_reset_token(self, expires_sec=1800):
        s = Serializer(app.config['SECRET_KEY'], expires_sec)
        return s.dumps({'user_id': self.id}).decode('utf-8')

    @staticmethod
    def verify_reset_token(token):
        s = Serializer(app.config['SECRET_KEY'])
        try:
            user_id = s.loads(token)['user_id']
        except:
            return None
        return User.query.get(user_id)

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tasks = db.relationship('Task', backref='project', lazy=True)
    shared_users = db.relationship('User', secondary=project_shares, backref=db.backref('projects_shared_with', lazy='dynamic'))

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(50), default='todo')  # possible values: todo, in_progress, done
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class PasswordReset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token = db.Column(db.String(200), unique=True, nullable=False)
    expires = db.Column(db.DateTime, nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get_or_404(int(user_id))

# =============================
# ROUTES
# =============================

@app.route('/')
@login_required
def dashboard():
    owned_projects = Project.query.filter_by(owner_id=current_user.id).all()
    shared_projects = current_user.shared_projects
    return render_template('dashboard.html', owned_projects=owned_projects, shared_projects=shared_projects)

@app.route('/login', methods=['GET', 'POST'])

def login():
    if request.method=='POST':
         username = request.form['username']
         password = request.form['password']
         user = User.query.filter_by(username=username).first()
         if user and user.check_password(password):
              login_user(user)
              return redirect(url_for('dashboard'))
         else:
              flash('Invalid credentials. Please try again.')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET','POST'])

def register():
    if request.method=='POST':
         username = request.form['username']
         email = request.form['email']
         password = request.form['password']
         # Check if a user with the same username or email exists
         if User.query.filter((User.username==username) | (User.email==email)).first():
              flash('User with this username or email already exists.')
         else:
             user = User(username=username, email=email)
             user.set_password(password)
             db.session.add(user)
             db.session.commit()
             flash('Registration successful. Please log in.')
             return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_request():
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()
        if user:
            token = user.get_reset_token()
            reset = PasswordReset(user_id=user.id, token=token, expires=datetime.utcnow() + timedelta(seconds=1800))
            db.session.add(reset)
            db.session.commit()
            # Send email here
            ses = boto3.client('ses', region_name=app.config['AWS_REGION_NAME'], 
                               aws_access_key_id=app.config['AWS_ACCESS_KEY_ID'],
                               aws_secret_access_key=app.config['AWS_SECRET_ACCESS_KEY'])
            ses.send_email(
                Source=app.config['SES_EMAIL_SOURCE'],
                Destination={'ToAddresses': [email]},
                Message={
                    'Subject': {'Data': 'Password Reset Request'},
                    'Body': {
                        'Text': {'Data': f'To reset your password, click on the following link: {url_for("reset_token", token=token, _external=True)}'}
                    }
                }
            )
            flash('Check your email for the instructions to reset your password')
            return redirect(url_for('login'))
        else:
            flash('Email not found')
    return render_template('reset_request.html')

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_token(token):
    reset = PasswordReset.query.filter_by(token=token).first()
    if reset is None or reset.expires < datetime.utcnow():
        flash('That is an invalid or expired token', 'warning')
        return redirect(url_for('reset_request'))
    if request.method == 'POST':
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('reset_token', token=token))
        user = User.query.get(reset.user_id)
        user.set_password(password)
        db.session.delete(reset)
        db.session.commit()
        flash('Your password has been updated! You are now able to log in')
        return redirect(url_for('login'))
    return render_template('reset_token.html')

# ---------- Project Routes ----------
@app.route('/projects/create', methods=['GET','POST'])
@login_required

def create_project():
    if request.method=='POST':
         name = request.form['name']
         description = request.form.get('description')
         project = Project(name=name, description=description, owner_id=current_user.id)
         db.session.add(project)
         db.session.commit()
         flash('Project created successfully.')
         return redirect(url_for('dashboard'))
    return render_template('create_project.html')

@app.route('/projects/<int:project_id>')
@login_required
def project_detail(project_id):
    project = Project.query.get_or_404(project_id)
    if current_user not in project.shared_users and project.owner != current_user:
         flash('Access denied.')
         return redirect(url_for('dashboard'))
    return render_template('project_detail.html', project=project)

@app.route('/projects/<int:project_id>/share', methods=['GET', 'POST'])
@login_required
def share_project(project_id):
    project = Project.query.get_or_404(project_id)
    if project.owner_id != current_user.id:
         flash('Only the project owner can share the project.')
         return redirect(url_for('dashboard'))
    if request.method == 'POST':
         username = request.form.get('username')
         user_to_share = User.query.filter_by(username=username).first()
         if not user_to_share:
              flash('User not found.')
         elif user_to_share == current_user:
              flash('You cannot share a project with yourself.')
         elif user_to_share in project.shared_users:
              flash('Project already shared with that user.')
         else:
              project.shared_users.append(user_to_share)
              db.session.commit()
              flash('Project shared successfully.')
         return redirect(url_for('project_detail', project_id=project.id))
    return render_template('share_project.html', project=project)

# ---------- Task Routes ----------
@app.route('/projects/<int:project_id>/tasks/create', methods=['GET','POST'])
@login_required

def create_task(project_id):
    project = Project.query.get_or_404(project_id)
    # Allow access if current user is owner or a shared user
    if current_user.id != project.owner_id and current_user not in project.shared_users:
         flash('Access denied.')
         return redirect(url_for('dashboard'))
    if request.method=='POST':
         title = request.form['title']
         description = request.form.get('description')
         task = Task(title=title, description=description, project_id=project.id, status='todo')
         assignee_username = request.form.get('assignee')
         if assignee_username:
              assignee_user = User.query.filter_by(username=assignee_username).first()
              if assignee_user and (assignee_user == project.owner or assignee_user in project.shared_users):
                  task.assigned_to_id = assignee_user.id
         db.session.add(task)
         db.session.commit()
         flash('Task created successfully.')
         return redirect(url_for('project_detail', project_id=project.id))
    potential_assignees = [project.owner] + project.shared_users
    return render_template('create_task.html', project=project, potential_assignees=potential_assignees)

@app.route('/tasks/<int:task_id>/update', methods=['GET','POST'])
@login_required

def update_task(task_id):
    task = Task.query.get_or_404(task_id)
    project = Project.query.get(task.project_id)
    if project.owner_id != current_user.id:
         flash('Access denied.')
         return redirect(url_for('dashboard'))
    if request.method=='POST':
         task.title = request.form['title']
         task.description = request.form.get('description')
         task.status = request.form.get('status')
         db.session.commit()
         flash('Task updated successfully.')
         return redirect(url_for('project_detail', project_id=project.id))
    return render_template('update_task.html', task=task)

@app.route('/tasks/<int:task_id>/delete', methods=['POST'])
@login_required

def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    project = Project.query.get(task.project_id)
    if project.owner_id != current_user.id:
         flash('Access denied.')
         return redirect(url_for('dashboard'))
    db.session.delete(task)
    db.session.commit()
    flash('Task deleted successfully.')
    return redirect(url_for('project_detail', project_id=project.id))

@app.route('/tasks/<int:task_id>/update_status', methods=['POST'])
@login_required
def update_task_status(task_id):
    task = Task.query.get_or_404(task_id)
    project = Project.query.get_or_404(task.project_id)
    if project.owner_id != current_user.id:
        return jsonify({"error": "Access denied"}), 403
    
    data = request.get_json()
    new_status = data.get('status', '').strip()
    print('[DEBUG] Received status update for task', task_id, 'with status:', new_status)
    if new_status not in ['todo', 'in_progress', 'done']:
        print('[DEBUG] Invalid status received:', new_status)
        return jsonify({"error": "Invalid status"}), 400
    
    task.status = new_status
    db.session.commit()
    
    return jsonify({"message": "Task status updated successfully"})

# =============================
# MAIN
# =============================
if __name__ == '__main__':
    if not os.path.exists('task_tracker.db'):
        with app.app_context():
            db.create_all()
    app.run(debug=True)