
import os
from decimal import Decimal
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, session
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename
from models import db, User, Item, Order, OrderItem
from config import Config
from functools import wraps

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    db.init_app(app)
    with app.app_context():
        db.create_all()

    login_manager = LoginManager(app)
    login_manager.login_view = 'login'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    def allowed_file(filename, allowed_exts):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_exts

    def get_cart():
        return session.setdefault('cart', {})

    def save_upload(file_storage):
        if not file_storage:
            return None
        filename = secure_filename(file_storage.filename)
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        base, ext = os.path.splitext(filename)
        i = 1
        while os.path.exists(path):
            filename = f"{base}_{i}{ext}"
            path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            i += 1
        file_storage.save(path)
        return filename

    def admin_required(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated or not current_user.is_admin:
                flash('Admins only', 'danger')
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return wrapper

    @app.route('/')
    def index():
        q = request.args.get('q', '').strip()
        items = Item.query
        if q:
            items = items.filter(Item.title.ilike(f"%{q}%"))
        items = items.order_by(Item.created_at.desc()).all()
        return render_template('index.html', items=items, q=q)

    @app.route('/uploads/<path:filename>')
    def uploaded_file(filename):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == 'POST':
            email = request.form['email'].strip().lower()
            password = request.form['password']
            if User.query.filter_by(email=email).first():
                flash('Email already registered', 'danger')
                return redirect(url_for('register'))
            user = User(email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash('Registration successful. Please login.', 'success')
            return redirect(url_for('login'))
        return render_template('register.html')

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            email = request.form['email'].strip().lower()
            password = request.form['password']
            user = User.query.filter_by(email=email).first()
            if user and user.check_password(password):
                login_user(user)
                flash('Logged in successfully', 'success')
                next_url = request.args.get('next') or url_for('index')
                return redirect(next_url)
            flash('Invalid credentials', 'danger')
        return render_template('login.html')

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('Logged out', 'info')
        return redirect(url_for('index'))

    @app.route('/add-to-cart/<int:item_id>', methods=['POST'])
    def add_to_cart(item_id):
        item = Item.query.get_or_404(item_id)
        cart = get_cart()
        cart[str(item_id)] = cart.get(str(item_id), 0) + int(request.form.get('qty', 1))
        session['cart'] = cart
        flash(f'Added {item.title} to cart', 'success')
        return redirect(url_for('index'))

    @app.route('/cart')
    def cart():
        cart = get_cart()
        ids = [int(i) for i in cart.keys()]
        items = Item.query.filter(Item.id.in_(ids)).all() if ids else []
        rows = []
        total = Decimal('0.00')
        for it in items:
            qty = int(cart.get(str(it.id), 0))
            line = Decimal(it.price) * qty
            total += line
            rows.append({'item': it, 'qty': qty, 'line_total': line})
        return render_template('cart.html', rows=rows, total=total)

    @app.route('/remove-from-cart/<int:item_id>', methods=['POST'])
    def remove_from_cart(item_id):
        cart = get_cart()
        cart.pop(str(item_id), None)
        session['cart'] = cart
        flash('Removed from cart', 'info')
        return redirect(url_for('cart'))

    @app.route('/checkout', methods=['POST'])
    @login_required
    def checkout():
        cart = get_cart()
        if not cart:
            flash('Cart is empty', 'warning')
            return redirect(url_for('cart'))
        ids = [int(i) for i in cart.keys()]
        items = Item.query.filter(Item.id.in_(ids)).all()
        if not items:
            flash('No items to checkout', 'warning')
            return redirect(url_for('cart'))

        order = Order(user_id=current_user.id, status='pending')
        db.session.add(order)
        db.session.flush()

        for it in items:
            qty = int(cart.get(str(it.id), 0))
            if qty < 1:
                continue
            db.session.add(OrderItem(order_id=order.id, item_id=it.id, quantity=qty, price_each=it.price))

        db.session.commit()
        session['cart'] = {}
        flash('Order submitted. Admin will review your request.', 'success')
        return redirect(url_for('index'))

    @app.route('/admin')
    @login_required
    @admin_required
    def admin_home():
        items_count = Item.query.count()
        orders_pending = Order.query.filter_by(status='pending').count()
        return render_template('admin_items.html', items=Item.query.order_by(Item.created_at.desc()).all(), items_count=items_count, orders_pending=orders_pending)

    @app.route('/admin/items')
    @login_required
    @admin_required
    def admin_items():
        items = Item.query.order_by(Item.created_at.desc()).all()
        return render_template('admin_items.html', items=items, items_count=len(items), orders_pending=Order.query.filter_by(status='pending').count())

    @app.route('/admin/items/new', methods=['GET', 'POST'])
    @login_required
    @admin_required
    def admin_item_new():
        if request.method == 'POST':
            title = request.form['title']
            price = Decimal(request.form['price'])
            description = request.form.get('description')
            video = request.files.get('video')
            filef = request.files.get('file')

            video_filename = None
            if video and allowed_file(video.filename, app.config['ALLOWED_VIDEO_EXT']):
                video_filename = save_upload(video)
            elif video and video.filename:
                flash('Invalid video format', 'danger')
                return redirect(request.url)

            file_filename = None
            if filef and allowed_file(filef.filename, app.config['ALLOWED_FILE_EXT']):
                file_filename = save_upload(filef)
            elif filef and filef.filename:
                flash('Invalid file format', 'danger')
                return redirect(request.url)

            item = Item(title=title, price=price, description=description, video_filename=video_filename, file_filename=file_filename)
            db.session.add(item)
            db.session.commit()
            flash('Item created', 'success')
            return redirect(url_for('admin_items'))
        return render_template('admin_item_form.html', item=None)

    @app.route('/admin/items/<int:item_id>/edit', methods=['GET', 'POST'])
    @login_required
    @admin_required
    def admin_item_edit(item_id):
        item = Item.query.get_or_404(item_id)
        if request.method == 'POST':
            item.title = request.form['title']
            item.price = Decimal(request.form['price'])
            item.description = request.form.get('description')

            video = request.files.get('video')
            if video and video.filename:
                if allowed_file(video.filename, app.config['ALLOWED_VIDEO_EXT']):
                    item.video_filename = save_upload(video)
                else:
                    flash('Invalid video format', 'danger')
                    return redirect(request.url)

            filef = request.files.get('file')
            if filef and filef.filename:
                if allowed_file(filef.filename, app.config['ALLOWED_FILE_EXT']):
                    item.file_filename = save_upload(filef)
                else:
                    flash('Invalid file format', 'danger')
                    return redirect(request.url)

            db.session.commit()
            flash('Item updated', 'success')
            return redirect(url_for('admin_items'))
        return render_template('admin_item_form.html', item=item)

    @app.route('/admin/items/<int:item_id>/delete', methods=['POST'])
    @login_required
    @admin_required
    def admin_item_delete(item_id):
        item = Item.query.get_or_404(item_id)
        db.session.delete(item)
        db.session.commit()
        flash('Item deleted', 'info')
        return redirect(url_for('admin_items'))

    @app.route('/admin/orders')
    @login_required
    @admin_required
    def admin_orders():
        orders = Order.query.order_by(Order.created_at.desc()).all()
        return render_template('admin_orders.html', orders=orders)

    @app.route('/admin/orders/<int:order_id>/status', methods=['POST'])
    @login_required
    @admin_required
    def admin_order_status(order_id):
        order = Order.query.get_or_404(order_id)
        new_status = request.form.get('status')
        if new_status in {'pending','approved','rejected','fulfilled'}:
            order.status = new_status
            db.session.commit()
            flash('Order status updated', 'success')
        else:
            flash('Invalid status', 'danger')
        return redirect(url_for('admin_orders'))

    return app

app = create_app()
