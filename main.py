# main.py
from flask import Flask, request, jsonify, session, render_template
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://admin:asdfghjkl@localhost/food_ordering_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Models
class User(db.Model):
    __tablename__ = 'Users'
    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    phone = db.Column(db.String(15))
    is_admin = db.Column(db.Boolean, default=False)
    registration_date = db.Column(db.DateTime, default=datetime.utcnow)
    orders = db.relationship('Order', backref='user', lazy=True)

class Dish(db.Model):
    __tablename__ = 'Dishes'
    dish_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    is_vegetarian = db.Column(db.Boolean, default=False)
    is_available = db.Column(db.Boolean, default=True)
    category = db.Column(db.String(50))

class Order(db.Model):
    __tablename__ = 'Orders'
    order_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('Users.user_id'), nullable=False)
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    delivery_address = db.Column(db.Text, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.Enum('Pending', 'Confirmed', 'Preparing', 'Ready for Pickup', 'Out for Delivery', 'Delivered', 'Rejected', 'Cancelled'), default='Pending')
    payment_method = db.Column(db.Enum('Credit Card', 'Debit Card', 'Cash on Delivery', 'Digital Wallet'), nullable=False)
    payment_status = db.Column(db.Boolean, default=False)
    rejection_reason = db.Column(db.Text)
    order_items = db.relationship('OrderItem', backref='order', lazy=True, cascade="all, delete-orphan")

class OrderItem(db.Model):
    __tablename__ = 'OrderItems'
    order_item_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order_id = db.Column(db.Integer, db.ForeignKey('Orders.order_id'), nullable=False)
    dish_id = db.Column(db.Integer, db.ForeignKey('Dishes.dish_id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    item_price = db.Column(db.Float, nullable=False)
    special_instructions = db.Column(db.Text)
    dish = db.relationship('Dish')

class Review(db.Model):
    __tablename__ = 'Reviews'
    review_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('Users.user_id'), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('Orders.order_id'))
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    review_date = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User')
    order = db.relationship('Order')

# Authentication decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'message': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'message': 'Authentication required'}), 401
        user = User.query.filter_by(user_id=session['user_id']).first()
        if not user or not user.is_admin:
            return jsonify({'message': 'Admin privileges required'}), 403
        return f(*args, **kwargs)
    return decorated_function

# Authentication routes
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'message': 'Username already exists'}), 409
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'message': 'Email already exists'}), 409
    hashed_password = generate_password_hash(data['password'])
    new_user = User(
        username=data['username'],
        password=hashed_password,
        email=data['email'],
        phone=data.get('phone', None),
        is_admin=data.get('is_admin', False)
    )
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'message': 'User registered successfully'}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(username=data['username']).first()
    if not user or not check_password_hash(user.password, data['password']):
        return jsonify({'message': 'Invalid credentials'}), 401
    session['user_id'] = user.user_id
    return jsonify({
        'message': 'Logged in successfully',
        'user': {
            'user_id': user.user_id,
            'username': user.username,
            'email': user.email,
            'is_admin': user.is_admin
        }
    }), 200

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify({'message': 'Logged out successfully'}), 200

# Dish routes
@app.route('/dishes', methods=['GET'])
def get_dishes():
    available = request.args.get('available')
    category = request.args.get('category')
    query = Dish.query
    if available and available.lower() == 'true':
        query = query.filter_by(is_available=True)
    if category:
        query = query.filter_by(category=category)
    dishes = query.all()
    return jsonify({
        'dishes': [{
            'dish_id': dish.dish_id,
            'name': dish.name,
            'description': dish.description,
            'price': dish.price,
            'is_vegetarian': dish.is_vegetarian,
            'is_available': dish.is_available,
            'category': dish.category
        } for dish in dishes]
    }), 200

@app.route('/dishes/<int:dish_id>', methods=['GET'])
def get_dish(dish_id):
    dish = Dish.query.get_or_404(dish_id)
    return jsonify({
        'dish_id': dish.dish_id,
        'name': dish.name,
        'description': dish.description,
        'price': dish.price,
        'is_vegetarian': dish.is_vegetarian,
        'is_available': dish.is_available,
        'category': dish.category
    }), 200

@app.route('/dishes', methods=['POST'])
@admin_required
def add_dish():
    data = request.get_json()
    new_dish = Dish(
        name=data['name'],
        description=data.get('description', ''),
        price=data['price'],
        is_vegetarian=data.get('is_vegetarian', False),
        is_available=data.get('is_available', True),
        category=data.get('category', '')
    )
    db.session.add(new_dish)
    db.session.commit()
    return jsonify({
        'message': 'Dish added successfully',
        'dish_id': new_dish.dish_id
    }), 201

@app.route('/dishes/<int:dish_id>', methods=['PUT'])
@admin_required
def update_dish(dish_id):
    dish = Dish.query.get_or_404(dish_id)
    data = request.get_json()
    dish.name = data.get('name', dish.name)
    dish.description = data.get('description', dish.description)
    dish.price = data.get('price', dish.price)
    dish.is_vegetarian = data.get('is_vegetarian', dish.is_vegetarian)
    dish.is_available = data.get('is_available', dish.is_available)
    dish.category = data.get('category', dish.category)
    db.session.commit()
    return jsonify({'message': 'Dish updated successfully'}), 200

@app.route('/dishes/<int:dish_id>', methods=['DELETE'])
@admin_required
def delete_dish(dish_id):
    dish = Dish.query.get_or_404(dish_id)
    db.session.delete(dish)
    db.session.commit()
    return jsonify({'message': 'Dish deleted successfully'}), 200

# Order routes
@app.route('/orders', methods=['POST'])
@login_required
def place_order():
    data = request.get_json()
    dishes_data = data.get('dishes', [])
    if not dishes_data:
        return jsonify({'message': 'Order must contain at least one dish'}), 400
    total_amount = 0
    order_items_data = []
    for dish_data in dishes_data:
        dish = Dish.query.get(dish_data['dish_id'])
        if not dish:
            return jsonify({'message': f"Dish with id {dish_data['dish_id']} not found"}), 404
        if not dish.is_available:
            return jsonify({'message': f"Dish '{dish.name}' is not available"}), 400
        quantity = dish_data.get('quantity', 1)
        item_price = dish.price
        total_amount += quantity * item_price
        order_items_data.append({
            'dish_id': dish.dish_id,
            'quantity': quantity,
            'item_price': item_price,
            'special_instructions': dish_data.get('special_instructions', '')
        })
    new_order = Order(
        user_id=session['user_id'],
        delivery_address=data['delivery_address'],
        total_amount=total_amount,
        payment_method=data['payment_method'],
        payment_status = False if data.get('payment_method') == 'Cash on Delivery' else True
    )
    db.session.add(new_order)
    db.session.flush()  # To obtain order_id
    for item_data in order_items_data:
        order_item = OrderItem(
            order_id=new_order.order_id,
            dish_id=item_data['dish_id'],
            quantity=item_data['quantity'],
            item_price=item_data['item_price'],
            special_instructions=item_data['special_instructions']
        )
        db.session.add(order_item)
    db.session.commit()
    return jsonify({
        'message': 'Order placed successfully',
        'order_id': new_order.order_id,
        'total_amount': new_order.total_amount
    }), 201

@app.route('/orders', methods=['GET'])
@login_required
def get_orders():
    user = User.query.get(session['user_id'])
    if user.is_admin:
        status = request.args.get('status')
        user_id = request.args.get('user_id')
        query = Order.query
        if status:
            query = query.filter_by(status=status)
        if user_id:
            query = query.filter_by(user_id=user_id)
        orders = query.order_by(Order.order_date.desc()).all()
    else:
        status = request.args.get('status')
        query = Order.query.filter_by(user_id=user.user_id)
        if status:
            query = query.filter_by(status=status)
        orders = query.order_by(Order.order_date.desc()).all()
    orders_data = []
    for order in orders:
        order_items = []
        for item in order.order_items:
            order_items.append({
                'dish_id': item.dish_id,
                'dish_name': item.dish.name,
                'quantity': item.quantity,
                'item_price': item.item_price,
                'special_instructions': item.special_instructions
            })
        orders_data.append({
            'order_id': order.order_id,
            'user_id': order.user_id,
            'username': order.user.username,
            'order_date': order.order_date.isoformat(),
            'delivery_address': order.delivery_address,
            'total_amount': order.total_amount,
            'status': order.status,
            'payment_method': order.payment_method,
            'payment_status': order.payment_status,
            'rejection_reason': order.rejection_reason,
            'items': order_items
        })
    return jsonify({'orders': orders_data}), 200

@app.route('/orders/<int:order_id>', methods=['GET'])
@login_required
def get_order(order_id):
    user = User.query.get(session['user_id'])
    order = Order.query.get_or_404(order_id)
    if not user.is_admin and order.user_id != user.user_id:
        return jsonify({'message': 'Access denied'}), 403
    order_items = []
    for item in order.order_items:
        order_items.append({
            'dish_id': item.dish_id,
            'dish_name': item.dish.name,
            'quantity': item.quantity,
            'item_price': item.item_price,
            'special_instructions': item.special_instructions
        })
    return jsonify({
        'order_id': order.order_id,
        'user_id': order.user_id,
        'username': order.user.username,
        'order_date': order.order_date.isoformat(),
        'delivery_address': order.delivery_address,
        'total_amount': order.total_amount,
        'status': order.status,
        'payment_method': order.payment_method,
        'payment_status': order.payment_status,
        'rejection_reason': order.rejection_reason,
        'items': order_items
    }), 200

@app.route('/orders/<int:order_id>/status', methods=['PUT'])
@admin_required
def update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    data = request.get_json()
    new_status = data.get('status')
    if not new_status:
        return jsonify({'message': 'Status is required'}), 400
    if new_status == 'Rejected' and not data.get('rejection_reason'):
        return jsonify({'message': 'Rejection reason is required'}), 400
    order.status = new_status
    if new_status == 'Rejected':
        order.rejection_reason = data.get('rejection_reason')
    db.session.commit()
    return jsonify({'message': f'Order status updated to {new_status}'}), 200

@app.route('/orders/<int:order_id>/cancel', methods=['PUT'])
@login_required
def cancel_order(order_id):
    user = User.query.get(session['user_id'])
    order = Order.query.get_or_404(order_id)
    if not user.is_admin and order.user_id != user.user_id:
        return jsonify({'message': 'Access denied'}), 403
    if order.status not in ['Pending', 'Confirmed']:
        return jsonify({'message': 'Cannot cancel order in current status'}), 400
    order.status = 'Cancelled'
    db.session.commit()
    return jsonify({'message': 'Order cancelled successfully'}), 200

# Review routes
@app.route('/reviews', methods=['POST'])
@login_required
def add_review():
    data = request.get_json()
    order_id = data.get('order_id')
    order = Order.query.get_or_404(order_id)
    if order.user_id != session['user_id']:
        return jsonify({'message': 'You can only review your own orders'}), 403
    if order.status != 'Delivered':
        return jsonify({'message': 'You can only review delivered orders'}), 400
    existing_review = Review.query.filter_by(order_id=order_id).first()
    if existing_review:
        return jsonify({'message': 'You have already reviewed this order'}), 400
    new_review = Review(
        user_id=session['user_id'],
        order_id=order_id,
        rating=data['rating'],
        comment=data.get('comment', '')
    )
    db.session.add(new_review)
    db.session.commit()
    return jsonify({'message': 'Review added successfully', 'review_id': new_review.review_id}), 201

@app.route('/reviews', methods=['GET'])
def get_reviews():
    reviews = Review.query.order_by(Review.review_date.desc()).all()
    reviews_data = []
    for review in reviews:
        reviews_data.append({
            'review_id': review.review_id,
            'user_id': review.user_id,
            'username': review.user.username,
            'order_id': review.order_id,
            'rating': review.rating,
            'comment': review.comment,
            'review_date': review.review_date.isoformat()
        })
    return jsonify({'reviews': reviews_data}), 200

@app.route('/admin_stats', methods=['GET'])
@admin_required
def admin_stats():
    from sqlalchemy import func

    total_orders = Order.query.count()
    total_revenue = db.session.query(func.sum(Order.total_amount)).scalar() or 0.0
    pending_orders = Order.query.filter_by(status='Pending').count()

    stats = {
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'pending_orders': pending_orders
    }
    return jsonify(stats), 200

@app.route('/orders/<int:order_id>/payment', methods=['PUT'])
@admin_required
def update_payment_status(order_id):
    order = Order.query.get_or_404(order_id)
    data = request.get_json()
    if 'payment_status' not in data:
        return jsonify({'message': 'Payment status is required'}), 400
    order.payment_status = data['payment_status']
    db.session.commit()
    status_text = 'Paid' if order.payment_status else 'Not Paid'
    return jsonify({'message': f'Payment status updated to {status_text}'}), 200

# Routes to serve HTML templates
@app.route('/')
def home():
    # Render the login page as the home page.
    return render_template('login.html')

@app.route('/index.html')
def index():
    return render_template('login.html')

@app.route('/admin_dashboard.html')
@admin_required
def admin_dashboard():
    return render_template('admin.html')

@app.route('/admin_menu.html')
@admin_required
def admin_menu():
    # You can create a dedicated admin menu page or reuse the customer menu layout.
    return render_template('admin_menu.html')

@app.route('/admin_orders.html')
@admin_required
def admin_orders():
    return render_template('admin_orders.html')

@app.route('/admin_reviews.html')
@admin_required
def admin_reviews():
    return render_template('admin_reviews.html')

@app.route('/menu.html')
@login_required
def menu_page():
    return render_template('menu.html')

@app.route('/my_orders.html')
@login_required
def orders_page():
    return render_template('orders.html')

@app.route('/reviews.html')
@login_required
def client_reviews():
    return render_template('reviews.html')

def initialize_app():
    with app.app_context():
        db.create_all()
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                password=generate_password_hash('admin123'),
                email='admin@restaurant.com',
                is_admin=True
            )
            db.session.add(admin)
            db.session.commit()
            print("Admin user created")
        else:
            print("Admin user already exists")

if __name__ == '__main__':
    initialize_app()
    app.run(debug=True)
