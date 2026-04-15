from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
from models import db, User, Announcement, Task, Attendance
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'oa-secret-key-2024')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///oa.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = '请先登录'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ── 初始化数据库 ──────────────────────────────────────────
def init_db():
    db.create_all()
    # 如果没有管理员，自动创建一个
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            password=generate_password_hash('admin123'),
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()
        print('已创建默认管理员账号: admin / admin123')

# ── 登录 / 注册 / 登出 ────────────────────────────────────
@app.route('/')
def index():
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('用户名或密码错误')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('用户名已存在')
        else:
            user = User(username=username, password=generate_password_hash(password))
            db.session.add(user)
            db.session.commit()
            flash('注册成功，请登录')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ── 首页仪表盘 ────────────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    announcements = Announcement.query.order_by(Announcement.created_at.desc()).limit(3).all()
    my_tasks = Task.query.filter_by(assignee_id=current_user.id, status='pending').all()
    today = date.today().strftime('%Y-%m-%d')
    checked_in = Attendance.query.filter_by(user_id=current_user.id, date=today).first()
    return render_template('dashboard.html',
                           announcements=announcements,
                           my_tasks=my_tasks,
                           checked_in=checked_in,
                           today=today)

# ── 公告 ──────────────────────────────────────────────────
@app.route('/announcements')
@login_required
def announcements():
    items = Announcement.query.order_by(Announcement.created_at.desc()).all()
    return render_template('announcements.html', announcements=items)

@app.route('/announcements/new', methods=['GET', 'POST'])
@login_required
def new_announcement():
    if not current_user.is_admin:
        flash('只有管理员可以发布公告')
        return redirect(url_for('announcements'))
    if request.method == 'POST':
        a = Announcement(
            title=request.form['title'],
            content=request.form['content'],
            author_id=current_user.id
        )
        db.session.add(a)
        db.session.commit()
        flash('公告发布成功')
        return redirect(url_for('announcements'))
    return render_template('announcement_form.html')

@app.route('/announcements/delete/<int:id>')
@login_required
def delete_announcement(id):
    if not current_user.is_admin:
        flash('无权限')
        return redirect(url_for('announcements'))
    a = Announcement.query.get_or_404(id)
    db.session.delete(a)
    db.session.commit()
    flash('公告已删除')
    return redirect(url_for('announcements'))

# ── 任务 ──────────────────────────────────────────────────
@app.route('/tasks')
@login_required
def tasks():
    if current_user.is_admin:
        items = Task.query.order_by(Task.created_at.desc()).all()
    else:
        items = Task.query.filter_by(assignee_id=current_user.id).order_by(Task.created_at.desc()).all()
    return render_template('tasks.html', tasks=items)

@app.route('/tasks/new', methods=['GET', 'POST'])
@login_required
def new_task():
    if not current_user.is_admin:
        flash('只有管理员可以创建任务')
        return redirect(url_for('tasks'))
    users = User.query.all()
    if request.method == 'POST':
        t = Task(
            title=request.form['title'],
            description=request.form['description'],
            assignee_id=request.form['assignee_id'],
            due_date=request.form['due_date'],
            creator_id=current_user.id
        )
        db.session.add(t)
        db.session.commit()
        flash('任务创建成功')
        return redirect(url_for('tasks'))
    return render_template('task_form.html', users=users)

@app.route('/tasks/done/<int:id>')
@login_required
def complete_task(id):
    t = Task.query.get_or_404(id)
    if t.assignee_id != current_user.id and not current_user.is_admin:
        flash('无权限')
        return redirect(url_for('tasks'))
    t.status = 'done'
    db.session.commit()
    flash('任务已标记为完成')
    return redirect(url_for('tasks'))

@app.route('/tasks/delete/<int:id>')
@login_required
def delete_task(id):
    if not current_user.is_admin:
        flash('无权限')
        return redirect(url_for('tasks'))
    t = Task.query.get_or_404(id)
    db.session.delete(t)
    db.session.commit()
    flash('任务已删除')
    return redirect(url_for('tasks'))

# ── 考勤 ──────────────────────────────────────────────────
@app.route('/attendance')
@login_required
def attendance():
    today = date.today().strftime('%Y-%m-%d')
    checked_in = Attendance.query.filter_by(user_id=current_user.id, date=today).first()
    if current_user.is_admin:
        records = Attendance.query.order_by(Attendance.date.desc()).limit(50).all()
    else:
        records = Attendance.query.filter_by(user_id=current_user.id).order_by(Attendance.date.desc()).all()
    return render_template('attendance.html', checked_in=checked_in, records=records, today=today)

@app.route('/attendance/checkin', methods=['POST'])
@login_required
def checkin():
    today = date.today().strftime('%Y-%m-%d')
    if Attendance.query.filter_by(user_id=current_user.id, date=today).first():
        flash('今天已经打卡了')
    else:
        now = datetime.now().strftime('%H:%M:%S')
        a = Attendance(
            user_id=current_user.id,
            date=today,
            check_in_time=now,
            note=request.form.get('note', '')
        )
        db.session.add(a)
        db.session.commit()
        flash(f'打卡成功！时间：{now}')
    return redirect(url_for('attendance'))

# ── 用户管理（仅管理员）────────────────────────────────────
@app.route('/users')
@login_required
def users():
    if not current_user.is_admin:
        flash('无权限')
        return redirect(url_for('dashboard'))
    all_users = User.query.all()
    return render_template('users.html', users=all_users)

@app.route('/users/toggle_admin/<int:id>')
@login_required
def toggle_admin(id):
    if not current_user.is_admin:
        flash('无权限')
        return redirect(url_for('dashboard'))
    u = User.query.get_or_404(id)
    if u.id != current_user.id:
        u.is_admin = not u.is_admin
        db.session.commit()
    return redirect(url_for('users'))

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
