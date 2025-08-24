from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from markdown2 import markdown
from datetime import timedelta
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired

app = Flask(__name__)
app.secret_key = 'your_secure_secret_key_here'  
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.permanent_session_lifetime = timedelta(minutes=30)

db = SQLAlchemy(app)


@app.template_filter('markdown')
def markdown_filter(text):
    return markdown(text, extras=['fenced-code-blocks', 'tables'])

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    bio = db.Column(db.Text, nullable=True)
    blogs = db.relationship('Blog', backref='author', lazy=True)
    comments = db.relationship('Comment', backref='author', lazy=True)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    blogs = db.relationship('Blog', backref='category', lazy=True)

class Blog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    comments = db.relationship('Comment', backref='blog', lazy=True)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    blog_id = db.Column(db.Integer, db.ForeignKey('blog.id'), nullable=False)


class BlogForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired()])
    content = TextAreaField('Content', validators=[DataRequired()])
    category = StringField('Category', validators=[DataRequired()])
    submit = SubmitField('Submit')

class CommentForm(FlaskForm):
    content = TextAreaField('Comment', validators=[DataRequired()])
    submit = SubmitField('Post Comment')


@app.route('/')
def home():
    query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    if query:
        blogs = Blog.query.filter(
            db.or_(
                Blog.title.ilike(f'%{query}%'),
                Blog.content.ilike(f'%{query}%'),
                Category.name.ilike(f'%{query}%')
            )
        ).join(Category).paginate(page=page, per_page=per_page)
    else:
        blogs = Blog.query.paginate(page=page, per_page=per_page)
    return render_template('home.html', blogs=blogs, query=query)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/technical-blogs')
def technical_blogs():
    page = request.args.get('page', 1, type=int)
    blogs = Blog.query.paginate(page=page, per_page=10)
    return render_template('technical_blogs.html', blogs=blogs)

@app.route('/profile/<username>')
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    page = request.args.get('page', 1, type=int)
    blogs = Blog.query.filter_by(user_id=user.id).paginate(page=page, per_page=10)
    return render_template('profile.html', user=user, blogs=blogs)

@app.route('/blog/<int:blog_id>', methods=['GET', 'POST'])
def blog_view(blog_id):
    blog = Blog.query.get_or_404(blog_id)
    form = CommentForm()
    if form.validate_on_submit() and session.get('user_id'):
        comment = Comment(content=form.content.data, user_id=session['user_id'], blog_id=blog_id)
        db.session.add(comment)
        db.session.commit()
        flash('Comment posted!', 'success')
        return redirect(url_for('blog_view', blog_id=blog_id))
    if not session.get('user_id'):
        flash('Login to comment', 'warning')
    return render_template('blog_view.html', blog=blog, form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session.permanent = True
            session['user_id'] = user.id
            session['username'] = user.username  # Ensure username is set
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        bio = request.form.get('bio', '')
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'warning')
        else:
            new_user = User(username=username, password=password, bio=bio)
            db.session.add(new_user)
            db.session.commit()
            flash('Registered successfully!', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if not session.get('user_id'):
        flash('Please login to access the dashboard', 'warning')
        return redirect(url_for('login'))
    user = db.session.get(User, session['user_id'])
    if not user:
        flash('User not found', 'danger')
        return redirect(url_for('logout'))
    page = request.args.get('page', 1, type=int)
    blogs = Blog.query.filter_by(user_id=user.id).paginate(page=page, per_page=10)
    return render_template('dashboard.html', username=user.username, blogs=blogs)

@app.route('/create-blog', methods=['GET', 'POST'])
def create_blog():
    if not session.get('user_id'):
        flash('Login required to create blog', 'warning')
        return redirect(url_for('login'))
    form = BlogForm()
    if form.validate_on_submit():
        category = Category.query.filter_by(name=form.category.data).first()
        if not category:
            category = Category(name=form.category.data)
            db.session.add(category)
            db.session.commit()
        blog = Blog(title=form.title.data, content=form.content.data, user_id=session['user_id'], category_id=category.id)
        db.session.add(blog)
        db.session.commit()
        flash('Blog created successfully!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('create_blog.html', form=form)

@app.route('/edit-blog/<int:blog_id>', methods=['GET', 'POST'])
def edit_blog(blog_id):
    blog = Blog.query.get_or_404(blog_id)
    if session.get('user_id') != blog.user_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('dashboard'))
    form = BlogForm(obj=blog)
    if form.validate_on_submit():
        category = Category.query.filter_by(name=form.category.data).first()
        if not category:
            category = Category(name=form.category.data)
            db.session.add(category)
            db.session.commit()
        blog.title = form.title.data
        blog.content = form.content.data
        blog.category_id = category.id
        db.session.commit()
        flash('Blog updated!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('edit_blog.html', form=form, blog=blog)

@app.route('/delete-blog/<int:blog_id>')
def delete_blog(blog_id):
    blog = Blog.query.get_or_404(blog_id)
    if session.get('user_id') != blog.user_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('dashboard'))
    db.session.delete(blog)
    db.session.commit()
    flash('Blog deleted.', 'info')
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('Logged out successfully', 'info')
    return redirect(url_for('home'))

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)