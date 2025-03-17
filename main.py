# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import mysql.connector
from mysql.connector import Error
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Database connection function
def create_connection():
    try:
        connection = mysql.connector.connect(
            host='localhost',
            database='food_ordering_db',
            user='admin',
            password='asdfghjkl'
        )
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

@app.context_processor
def inject_logged_in():
    return dict(logged_in=('user_id' in session))

# Home page
@app.route('/')
def home():
    connection = create_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        
        # Get restaurants
        cursor.execute("SELECT * FROM Restaurants WHERE is_active = TRUE")
        restaurants = cursor.fetchall()
        
        # Get categories
        cursor.execute("SELECT * FROM Categories")
        categories = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return render_template('index.html', 
                              restaurants=restaurants, 
                              categories=categories, 
                              logged_in='user_id' in session)
    return "Database connection error", 500

# User registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        phone = request.form['phone']
        address = request.form['address']
        
        # Check if username or email exists
        connection = create_connection()
        if connection:
            cursor = connection.cursor()
            cursor.execute("SELECT * FROM Users WHERE username = %s OR email = %s", (username, email))
            existing_user = cursor.fetchone()
            
            if existing_user:
                cursor.close()
                connection.close()
                flash("Username or email already exists!")
                return redirect(url_for('register'))
            
            # Create new user
            hashed_password = generate_password_hash(password)
            cursor.execute(
                "INSERT INTO Users (username, password, email, phone, address) VALUES (%s, %s, %s, %s, %s)",
                (username, hashed_password, email, phone, address)
            )
            connection.commit()
            cursor.close()
            connection.close()
            
            flash("Registration successful! Please log in.")
            return redirect(url_for('login'))
        
        return "Database connection error", 500
        
    return render_template('register.html')

# User login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        connection = create_connection()
        if connection:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM Users WHERE username = %s", (username,))
            user = cursor.fetchone()
            cursor.close()
            connection.close()
            
            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['user_id']
                session['username'] = user['username']
                flash("Login successful!")
                return redirect(url_for('home'))
            else:
                flash("Invalid username or password!")
                
        else:
            flash("Database connection error!")
            
    return render_template('login.html')

# Logout
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash("You have been logged out.")
    return redirect(url_for('home'))

# Restaurant menu
@app.route('/restaurant/<int:restaurant_id>')
def restaurant_menu(restaurant_id):
    connection = create_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        
        # Get restaurant info
        cursor.execute("SELECT * FROM Restaurants WHERE restaurant_id = %s", (restaurant_id,))
        restaurant = cursor.fetchone()
        
        if not restaurant:
            cursor.close()
            connection.close()
            flash("Restaurant not found!")
            return redirect(url_for('home'))
        
        # Get menu items grouped by category
        cursor.execute("""
            SELECT m.*, c.name as category_name 
            FROM MenuItems m 
            LEFT JOIN Categories c ON m.category_id = c.category_id 
            WHERE m.restaurant_id = %s AND m.is_available = TRUE
            ORDER BY c.name, m.name
        """, (restaurant_id,))
        
        menu_items = cursor.fetchall()
        
        # Group items by category
        categories = {}
        for item in menu_items:
            category = item['category_name'] or 'Uncategorized'
            if category not in categories:
                categories[category] = []
            categories[category].append(item)
        
        cursor.close()
        connection.close()
        
        return render_template('restaurant.html', 
                              restaurant=restaurant, 
                              categories=categories, 
                              logged_in='user_id' in session)
    
    return "Database connection error", 500

# Add to cart functionality
@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    if 'user_id' not in session:
        flash('Please log in first!')
        return redirect(url_for('login'))
    
    item_id = request.form.get('item_id')
    quantity = int(request.form.get('quantity', 1))
    
    if 'cart' not in session:
        session['cart'] = []
    
    connection = create_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT m.*, r.restaurant_id, r.name as restaurant_name 
            FROM MenuItems m
            JOIN Restaurants r ON m.restaurant_id = r.restaurant_id
            WHERE m.item_id = %s
        """, (item_id,))
        
        item = cursor.fetchone()
        cursor.close()
        connection.close()
        
        if not item:
            flash('Item not found!')
            return redirect(url_for('home'))
        
        if session['cart'] and session['cart'][0]['restaurant_id'] != item['restaurant_id']:
            flash('Your cart contains items from another restaurant. Clear your cart first!')
            return redirect(url_for('home'))
        
        for cart_item in session['cart']:
            if cart_item['item_id'] == int(item_id):
                cart_item['quantity'] += quantity
                session.modified = True
                flash(f"Added {quantity} more {item['name']} to your cart.")
                return redirect(url_for('view_cart'))
        
        cart_item = {
            'item_id': item['item_id'],
            'name': item['name'],
            'price': float(item['price']),
            'quantity': quantity,
            'restaurant_id': item['restaurant_id'],
            'restaurant_name': item['restaurant_name']
        }
        
        session['cart'].append(cart_item)
        session.modified = True
        flash(f"Added {item['name']} to your cart.")
        return redirect(url_for('view_cart'))
    
    flash('Database error!')
    return redirect(url_for('home'))

# View cart
@app.route('/cart')
def view_cart():
    cart = session.get('cart', [])
    cart_total = sum(item['price'] * item['quantity'] for item in cart)
    return render_template('cart.html', cart=cart, cart_total=cart_total)

# Remove from cart
@app.route('/remove_from_cart/<int:item_id>')
def remove_from_cart(item_id):
    if 'cart' in session:
        session['cart'] = [item for item in session['cart'] if item['item_id'] != item_id]
        session.modified = True
    return redirect(url_for('view_cart'))

# Checkout page
@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if 'user_id' not in session:
        flash("Please log in to checkout")
        return redirect(url_for('login'))
    
    if not session.get('cart'):
        flash("Your cart is empty!")
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        user_id = session['user_id']
        delivery_address = request.form['address']
        payment_method = request.form['payment_method']
        restaurant_id = session['cart'][0]['restaurant_id']
        total_amount = sum(item['price'] * item['quantity'] for item in session['cart'])
        
        connection = create_connection()
        if connection:
            try:
                cursor = connection.cursor()
                
                # Start transaction
                connection.start_transaction()
                
                # Create order
                cursor.execute("""
                    INSERT INTO Orders (user_id, restaurant_id, delivery_address, total_amount, payment_method)
                    VALUES (%s, %s, %s, %s, %s)
                """, (user_id, restaurant_id, delivery_address, total_amount, payment_method))
                
                order_id = cursor.lastrowid
                
                # Add order items
                for item in session['cart']:
                    cursor.execute("""
                        INSERT INTO OrderItems (order_id, item_id, quantity, item_price)
                        VALUES (%s, %s, %s, %s)
                    """, (order_id, item['item_id'], item['quantity'], item['price']))
                
                # Commit transaction
                connection.commit()
                
                # Clear cart
                session.pop('cart', None)
                
                flash("Order placed successfully!")
                return redirect(url_for('order_confirmation', order_id=order_id))
                
            except Error as e:
                # Rollback in case of error
                connection.rollback()
                print(f"Database error: {e}")
                flash("Error processing your order. Please try again.")
                
            finally:
                cursor.close()
                connection.close()
        
        else:
            flash("Database connection error")
            
    # GET method - show checkout form
    user = None
    if 'user_id' in session:
        connection = create_connection()
        if connection:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM Users WHERE user_id = %s", (session['user_id'],))
            user = cursor.fetchone()
            cursor.close()
            connection.close()
    
    cart = session.get('cart', [])
    cart_total = sum(item['price'] * item['quantity'] for item in cart)
    return render_template('checkout.html', cart=cart, cart_total=cart_total, user=user)

# Order confirmation
@app.route('/order_confirmation/<int:order_id>')
def order_confirmation(order_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    connection = create_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        
        # Get order details
        cursor.execute("""
            SELECT o.*, r.name as restaurant_name
            FROM Orders o
            JOIN Restaurants r ON o.restaurant_id = r.restaurant_id
            WHERE o.order_id = %s AND o.user_id = %s
        """, (order_id, session['user_id']))
        
        order = cursor.fetchone()
        
        if not order:
            cursor.close()
            connection.close()
            flash("Order not found!")
            return redirect(url_for('my_orders'))
        
        # Get order items
        cursor.execute("""
            SELECT oi.*, m.name
            FROM OrderItems oi
            JOIN MenuItems m ON oi.item_id = m.item_id
            WHERE oi.order_id = %s
        """, (order_id,))
        
        order_items = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return render_template('order_confirmation.html', order=order, items=order_items)
    
    return "Database connection error", 500

# User orders
@app.route('/my_orders')
def my_orders():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    connection = create_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        
        # Get user orders
        cursor.execute("""
            SELECT o.*, r.name as restaurant_name
            FROM Orders o
            JOIN Restaurants r ON o.restaurant_id = r.restaurant_id
            WHERE o.user_id = %s
            ORDER BY o.order_date DESC
        """, (session['user_id'],))
        
        orders = cursor.fetchall()
        cursor.close()
        connection.close()
        
        return render_template('my_orders.html', orders=orders)
    
    return "Database connection error", 500

# View order details
@app.route('/order/<int:order_id>')
def view_order(order_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    connection = create_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        
        # Get order details
        cursor.execute("""
            SELECT o.*, r.name as restaurant_name
            FROM Orders o
            JOIN Restaurants r ON o.restaurant_id = r.restaurant_id
            WHERE o.order_id = %s AND o.user_id = %s
        """, (order_id, session['user_id']))
        
        order = cursor.fetchone()
        
        if not order:
            cursor.close()
            connection.close()
            flash("Order not found!")
            return redirect(url_for('my_orders'))
        
        # Get order items
        cursor.execute("""
            SELECT oi.*, m.name
            FROM OrderItems oi
            JOIN MenuItems m ON oi.item_id = m.item_id
            WHERE oi.order_id = %s
        """, (order_id,))
        
        order_items = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return render_template('order_details.html', order=order, items=order_items)
    
    return "Database connection error", 500

# Add review
@app.route('/add_review/<int:order_id>', methods=['GET', 'POST'])
def add_review(order_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    connection = create_connection()
    if not connection:
        flash("Database connection error")
        return redirect(url_for('my_orders'))
    
    cursor = connection.cursor(dictionary=True)
    
    # Verify order belongs to user and get restaurant_id
    cursor.execute("""
        SELECT o.*, r.name as restaurant_name
        FROM Orders o
        JOIN Restaurants r ON o.restaurant_id = r.restaurant_id
        WHERE o.order_id = %s AND o.user_id = %s AND o.status = 'Delivered'
    """, (order_id, session['user_id']))
    
    order = cursor.fetchone()
    
    if not order:
        cursor.close()
        connection.close()
        flash("Order not found or not eligible for review!")
        return redirect(url_for('my_orders'))
    
    # Check if review already exists
    cursor.execute("""
        SELECT * FROM Reviews 
        WHERE order_id = %s AND user_id = %s
    """, (order_id, session['user_id']))
    
    existing_review = cursor.fetchone()
    
    if request.method == 'POST':
        rating = int(request.form['rating'])
        comment = request.form['comment']
        
        try:
            if existing_review:
                # Update existing review
                cursor.execute("""
                    UPDATE Reviews 
                    SET rating = %s, comment = %s, review_date = CURRENT_TIMESTAMP
                    WHERE review_id = %s
                """, (rating, comment, existing_review['review_id']))
                flash("Review updated successfully!")
            else:
                # Add new review
                cursor.execute("""
                    INSERT INTO Reviews (user_id, restaurant_id, order_id, rating, comment)
                    VALUES (%s, %s, %s, %s, %s)
                """, (session['user_id'], order['restaurant_id'], order_id, rating, comment))
                flash("Review added successfully!")
            
            # Update restaurant average rating
            cursor.execute("""
                UPDATE Restaurants 
                SET avg_rating = (
                    SELECT AVG(rating) 
                    FROM Reviews 
                    WHERE restaurant_id = %s
                )
                WHERE restaurant_id = %s
            """, (order['restaurant_id'], order['restaurant_id']))
            
            connection.commit()
            
            return redirect(url_for('view_order', order_id=order_id))
            
        except Error as e:
            connection.rollback()
            print(f"Database error: {e}")
            flash("Error processing your review. Please try again.")
        
    cursor.close()
    connection.close()
    
    return render_template('add_review.html', order=order, existing_review=existing_review)

# Admin routes - Restaurant Management
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # For simplicity, using hardcoded admin credentials
        # In a production environment, you should store admin users in the database
        if username == 'admin' and password == 'admin123':
            session['admin'] = True
            flash("Admin login successful!")
            return redirect(url_for('admin_dashboard'))
        else:
            flash("Invalid admin credentials!")
    
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    flash("Admin logged out successfully!")
    return redirect(url_for('admin_login'))

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    
    connection = create_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        
        # Get statistics
        cursor.execute("SELECT COUNT(*) as total_restaurants FROM Restaurants")
        restaurant_count = cursor.fetchone()['total_restaurants']
        
        cursor.execute("SELECT COUNT(*) as total_users FROM Users")
        user_count = cursor.fetchone()['total_users']
        
        cursor.execute("SELECT COUNT(*) as total_orders FROM Orders")
        order_count = cursor.fetchone()['total_orders']
        
        cursor.execute("""
            SELECT status, COUNT(*) as count 
            FROM Orders 
            GROUP BY status
        """)
        order_status = cursor.fetchall()
        
        cursor.execute("""
            SELECT DATE(order_date) as date, COUNT(*) as orders, SUM(total_amount) as revenue
            FROM Orders
            WHERE order_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            GROUP BY DATE(order_date)
            ORDER BY date
        """)
        daily_stats = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return render_template('admin_dashboard.html', 
                              restaurant_count=restaurant_count,
                              user_count=user_count,
                              order_count=order_count,
                              order_status=order_status,
                              daily_stats=daily_stats)
    
    return "Database connection error", 500

@app.route('/admin/restaurants')
def admin_restaurants():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    
    connection = create_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT r.*, COUNT(DISTINCT m.item_id) as menu_items, COUNT(DISTINCT o.order_id) as orders
            FROM Restaurants r
            LEFT JOIN MenuItems m ON r.restaurant_id = m.restaurant_id
            LEFT JOIN Orders o ON r.restaurant_id = o.restaurant_id
            GROUP BY r.restaurant_id
            ORDER BY r.name
        """)
        
        restaurants = cursor.fetchall()
        cursor.close()
        connection.close()
        
        return render_template('admin_restaurants.html', restaurants=restaurants)
    
    return "Database connection error", 500

@app.route('/admin/restaurant/add', methods=['GET', 'POST'])
def admin_add_restaurant():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        address = request.form['address']
        phone = request.form['phone']
        opening_time = request.form['opening_time']
        closing_time = request.form['closing_time']
        
        connection = create_connection()
        if connection:
            try:
                cursor = connection.cursor()
                
                cursor.execute("""
                    INSERT INTO Restaurants (name, description, address, phone, opening_time, closing_time)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (name, description, address, phone, opening_time, closing_time))
                
                connection.commit()
                flash("Restaurant added successfully!")
                return redirect(url_for('admin_restaurants'))
                
            except Error as e:
                connection.rollback()
                print(f"Database error: {e}")
                flash("Error adding restaurant. Please try again.")
                
            finally:
                cursor.close()
                connection.close()
    
    return render_template('admin_add_restaurant.html')

@app.route('/admin/restaurant/edit/<int:restaurant_id>', methods=['GET', 'POST'])
def admin_edit_restaurant(restaurant_id):
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    
    connection = create_connection()
    if not connection:
        flash("Database connection error")
        return redirect(url_for('admin_restaurants'))
    
    cursor = connection.cursor(dictionary=True)
    
    # Get restaurant details
    cursor.execute("SELECT * FROM Restaurants WHERE restaurant_id = %s", (restaurant_id,))
    restaurant = cursor.fetchone()
    
    if not restaurant:
        cursor.close()
        connection.close()
        flash("Restaurant not found!")
        return redirect(url_for('admin_restaurants'))
    
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        address = request.form['address']
        phone = request.form['phone']
        opening_time = request.form['opening_time']
        closing_time = request.form['closing_time']
        is_active = 'is_active' in request.form
        
        try:
            cursor.execute("""
                UPDATE Restaurants
                SET name = %s, description = %s, address = %s, phone = %s, 
                    opening_time = %s, closing_time = %s, is_active = %s
                WHERE restaurant_id = %s
            """, (name, description, address, phone, opening_time, closing_time, is_active, restaurant_id))
            
            connection.commit()
            flash("Restaurant updated successfully!")
            return redirect(url_for('admin_restaurants'))
            
        except Error as e:
            connection.rollback()
            print(f"Database error: {e}")
            flash("Error updating restaurant. Please try again.")
    
    cursor.close()
    connection.close()
    
    return render_template('admin_edit_restaurant.html', restaurant=restaurant)

@app.route('/admin/restaurant/delete/<int:restaurant_id>')
def admin_delete_restaurant(restaurant_id):
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    
    connection = create_connection()
    if connection:
        try:
            cursor = connection.cursor()
            
            # Check if restaurant has orders
            cursor.execute("SELECT COUNT(*) FROM Orders WHERE restaurant_id = %s", (restaurant_id,))
            order_count = cursor.fetchone()[0]
            
            if order_count > 0:
                flash("Cannot delete restaurant with existing orders. Deactivate it instead.")
                return redirect(url_for('admin_restaurants'))
            
            # Delete restaurant and related menu items (using CASCADE)
            cursor.execute("DELETE FROM Restaurants WHERE restaurant_id = %s", (restaurant_id,))
            
            connection.commit()
            flash("Restaurant deleted successfully!")
            
        except Error as e:
            connection.rollback()
            print(f"Database error: {e}")
            flash("Error deleting restaurant.")
            
        finally:
            cursor.close()
            connection.close()
    
    return redirect(url_for('admin_restaurants'))

@app.route('/admin/menu/<int:restaurant_id>')
def admin_menu(restaurant_id):
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    
    connection = create_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        
        # Get restaurant info
        cursor.execute("SELECT * FROM Restaurants WHERE restaurant_id = %s", (restaurant_id,))
        restaurant = cursor.fetchone()
        
        if not restaurant:
            cursor.close()
            connection.close()
            flash("Restaurant not found!")
            return redirect(url_for('admin_restaurants'))
        
        # Get menu items
        cursor.execute("""
            SELECT m.*, c.name as category_name 
            FROM MenuItems m 
            LEFT JOIN Categories c ON m.category_id = c.category_id 
            WHERE m.restaurant_id = %s
            ORDER BY c.name, m.name
        """, (restaurant_id,))
        
        menu_items = cursor.fetchall()
        
        # Get categories for dropdown
        cursor.execute("SELECT * FROM Categories ORDER BY name")
        categories = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return render_template('admin_menu.html', 
                              restaurant=restaurant, 
                              menu_items=menu_items,
                              categories=categories)
    
    return "Database connection error", 500

@app.route('/admin/menu/add/<int:restaurant_id>', methods=['GET', 'POST'])
def admin_add_menu_item(restaurant_id):
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    
    connection = create_connection()
    if not connection:
        flash("Database connection error")
        return redirect(url_for('admin_restaurants'))
    
    cursor = connection.cursor(dictionary=True)
    
    # Get restaurant info
    cursor.execute("SELECT * FROM Restaurants WHERE restaurant_id = %s", (restaurant_id,))
    restaurant = cursor.fetchone()
    
    if not restaurant:
        cursor.close()
        connection.close()
        flash("Restaurant not found!")
        return redirect(url_for('admin_restaurants'))
    
    # Get categories for dropdown
    cursor.execute("SELECT * FROM Categories ORDER BY name")
    categories = cursor.fetchall()
    
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = float(request.form['price'])
        category_id = request.form.get('category_id') or None
        is_vegetarian = 'is_vegetarian' in request.form
        is_available = 'is_available' in request.form
        image_url = request.form.get('image_url') or None
        
        try:
            cursor.execute("""
                INSERT INTO MenuItems (restaurant_id, category_id, name, description, price, is_vegetarian, is_available, image_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (restaurant_id, category_id, name, description, price, is_vegetarian, is_available, image_url))
            
            connection.commit()
            flash("Menu item added successfully!")
            return redirect(url_for('admin_menu', restaurant_id=restaurant_id))
            
        except Error as e:
            connection.rollback()
            print(f"Database error: {e}")
            flash("Error adding menu item. Please try again.")
    
    cursor.close()
    connection.close()
    
    return render_template('admin_add_menu_item.html', restaurant=restaurant, categories=categories)

@app.route('/admin/menu/edit/<int:item_id>', methods=['GET', 'POST'])
def admin_edit_menu_item(item_id):
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    
    connection = create_connection()
    if not connection:
        flash("Database connection error")
        return redirect(url_for('admin_restaurants'))
    
    cursor = connection.cursor(dictionary=True)
    
    # Get menu item details
    cursor.execute("""
        SELECT m.*, r.name as restaurant_name 
        FROM MenuItems m
        JOIN Restaurants r ON m.restaurant_id = r.restaurant_id
        WHERE m.item_id = %s
    """, (item_id,))
    
    menu_item = cursor.fetchone()
    
    if not menu_item:
        cursor.close()
        connection.close()
        flash("Menu item not found!")
        return redirect(url_for('admin_restaurants'))
    
    # Get categories for dropdown
    cursor.execute("SELECT * FROM Categories ORDER BY name")
    categories = cursor.fetchall()
    
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = float(request.form['price'])
        category_id = request.form.get('category_id') or None
        is_vegetarian = 'is_vegetarian' in request.form
        is_available = 'is_available' in request.form
        image_url = request.form.get('image_url') or None
        
        try:
            cursor.execute("""
                UPDATE MenuItems
                SET name = %s, description = %s, price = %s, category_id = %s, 
                    is_vegetarian = %s, is_available = %s, image_url = %s
                WHERE item_id = %s
            """, (name, description, price, category_id, is_vegetarian, is_available, image_url, item_id))
            
            connection.commit()
            flash("Menu item updated successfully!")
            return redirect(url_for('admin_menu', restaurant_id=menu_item['restaurant_id']))
            
        except Error as e:
            connection.rollback()
            print(f"Database error: {e}")
            flash("Error updating menu item. Please try again.")
    
    cursor.close()
    connection.close()
    
    return render_template('admin_edit_menu_item.html', item=menu_item, categories=categories)

@app.route('/admin/menu/delete/<int:item_id>')
def admin_delete_menu_item(item_id):
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    
    connection = create_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Get restaurant_id for redirection
            cursor.execute("SELECT restaurant_id FROM MenuItems WHERE item_id = %s", (item_id,))
            menu_item = cursor.fetchone()
            
            if not menu_item:
                flash("Menu item not found!")
                return redirect(url_for('admin_restaurants'))
            
            restaurant_id = menu_item['restaurant_id']
            
            # Check if menu item has orders
            cursor.execute("SELECT COUNT(*) as count FROM OrderItems WHERE item_id = %s", (item_id,))
            order_count = cursor.fetchone()['count']
            
            if order_count > 0:
                flash("Cannot delete menu item with existing orders. Mark it as unavailable instead.")
                return redirect(url_for('admin_menu', restaurant_id=restaurant_id))
            
            # Delete menu item
            cursor.execute("DELETE FROM MenuItems WHERE item_id = %s", (item_id,))
            
            connection.commit()
            flash("Menu item deleted successfully!")
            return redirect(url_for('admin_menu', restaurant_id=restaurant_id))
            
        except Error as e:
            connection.rollback()
            print(f"Database error: {e}")
            flash("Error deleting menu item.")
            
        finally:
            cursor.close()
            connection.close()
    
    return redirect(url_for('admin_restaurants'))

@app.route('/admin/categories')
def admin_categories():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    
    connection = create_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT c.*, COUNT(m.item_id) as item_count
            FROM Categories c
            LEFT JOIN MenuItems m ON c.category_id = m.category_id
            GROUP BY c.category_id
            ORDER BY c.name
        """)
        
        categories = cursor.fetchall()
        cursor.close()
        connection.close()
        
        return render_template('admin_categories.html', categories=categories)
    
    return "Database connection error", 500

@app.route('/admin/category/add', methods=['GET', 'POST'])
def admin_add_category():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        
        connection = create_connection()
        if connection:
            try:
                cursor = connection.cursor()
                
                cursor.execute("""
                    INSERT INTO Categories (name, description)
                    VALUES (%s, %s)
                """, (name, description))
                
                connection.commit()
                flash("Category added successfully!")
                return redirect(url_for('admin_categories'))
                
            except Error as e:
                connection.rollback()
                print(f"Database error: {e}")
                flash("Error adding category. Please try again.")
                
            finally:
                cursor.close()
                connection.close()
    
    return render_template('admin_add_category.html')

@app.route('/admin/category/edit/<int:category_id>', methods=['GET', 'POST'])
def admin_edit_category(category_id):
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    
    connection = create_connection()
    if not connection:
        flash("Database connection error")
        return redirect(url_for('admin_categories'))
    
    cursor = connection.cursor(dictionary=True)
    
    # Get category details
    cursor.execute("SELECT * FROM Categories WHERE category_id = %s", (category_id,))
    category = cursor.fetchone()
    
    if not category:
        cursor.close()
        connection.close()
        flash("Category not found!")
        return redirect(url_for('admin_categories'))
    
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        
        try:
            cursor.execute("""
                UPDATE Categories
                SET name = %s, description = %s
                WHERE category_id = %s
            """, (name, description, category_id))
            
            connection.commit()
            flash("Category updated successfully!")
            return redirect(url_for('admin_categories'))
            
        except Error as e:
            connection.rollback()
            print(f"Database error: {e}")
            flash("Error updating category. Please try again.")
    
    cursor.close()
    connection.close()
    
    return render_template('admin_edit_category.html', category=category)

@app.route('/admin/category/delete/<int:category_id>')
def admin_delete_category(category_id):
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    
    connection = create_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Check if category has menu items
            cursor.execute("SELECT COUNT(*) as count FROM MenuItems WHERE category_id = %s", (category_id,))
            item_count = cursor.fetchone()['count']
            
            if item_count > 0:
                flash(f"Cannot delete category with {item_count} menu items. Reassign menu items first.")
                return redirect(url_for('admin_categories'))
            
            # Delete category
            cursor.execute("DELETE FROM Categories WHERE category_id = %s", (category_id,))
            
            connection.commit()
            flash("Category deleted successfully!")
            
        except Error as e:
            connection.rollback()
            print(f"Database error: {e}")
            flash("Error deleting category.")
            
        finally:
            cursor.close()
            connection.close()
    
    return redirect(url_for('admin_categories'))

@app.route('/admin/orders')
def admin_orders():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    
    # Get filter params
    status = request.args.get('status', '')
    restaurant_id = request.args.get('restaurant_id', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    connection = create_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        
        # Get restaurants for filter dropdown
        cursor.execute("SELECT restaurant_id, name FROM Restaurants ORDER BY name")
        restaurants = cursor.fetchall()
        
        # Build query with filters
        query = """
            SELECT o.*, u.username, r.name as restaurant_name
            FROM Orders o
            JOIN Users u ON o.user_id = u.user_id
            JOIN Restaurants r ON o.restaurant_id = r.restaurant_id
            WHERE 1=1
        """
        params = []
        
        if status:
            query += " AND o.status = %s"
            params.append(status)
        
        if restaurant_id:
            query += " AND o.restaurant_id = %s"
            params.append(restaurant_id)
        
        if date_from:
            query += " AND DATE(o.order_date) >= %s"
            params.append(date_from)
        
        if date_to:
            query += " AND DATE(o.order_date) <= %s"
            params.append(date_to)
        
        query += " ORDER BY o.order_date DESC"
        
        cursor.execute(query, params)
        orders = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return render_template('admin_orders.html', 
                              orders=orders, 
                              restaurants=restaurants,
                              current_status=status,
                              current_restaurant=restaurant_id,
                              date_from=date_from,
                              date_to=date_to)
    
    return "Database connection error", 500

@app.route('/admin/order/<int:order_id>')
def admin_view_order(order_id):
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    
    connection = create_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        
        # Get order details
        cursor.execute("""
            SELECT o.*, u.username, u.email, u.phone, r.name as restaurant_name
            FROM Orders o
            JOIN Users u ON o.user_id = u.user_id
            JOIN Restaurants r ON o.restaurant_id = r.restaurant_id
            WHERE o.order_id = %s
        """, (order_id,))
        
        order = cursor.fetchone()
        
        if not order:
            cursor.close()
            connection.close()
            flash("Order not found!")
            return redirect(url_for('admin_orders'))
        
        # Get order items
        cursor.execute("""
            SELECT oi.*, m.name
            FROM OrderItems oi
            JOIN MenuItems m ON oi.item_id = m.item_id
            WHERE oi.order_id = %s
        """, (order_id,))
        
        order_items = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return render_template('admin_order_details.html', order=order, items=order_items)
    
    return "Database connection error", 500

@app.route('/admin/order/update_status/<int:order_id>', methods=['POST'])
def admin_update_order_status(order_id):
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    
    status = request.form['status']
    
    connection = create_connection()
    if connection:
        try:
            cursor = connection.cursor()
            
            cursor.execute("""
                UPDATE Orders
                SET status = %s
                WHERE order_id = %s
            """, (status, order_id))
            
            connection.commit()
            flash("Order status updated successfully!")
            
        except Error as e:
            connection.rollback()
            print(f"Database error: {e}")
            flash("Error updating order status.")
            
        finally:
            cursor.close()
            connection.close()
    
    return redirect(url_for('admin_view_order', order_id=order_id))

@app.route('/admin/promotions')
def admin_promotions():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    
    connection = create_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT p.*, COUNT(rp.restaurant_id) as restaurant_count
            FROM Promotions p
            LEFT JOIN RestaurantPromotions rp ON p.promo_id = rp.promo_id
            GROUP BY p.promo_id
            ORDER BY p.end_date DESC
        """)
        
        promotions = cursor.fetchall()
        cursor.close()
        connection.close()
        
        return render_template('admin_promotions.html', promotions=promotions)
    
    return "Database connection error", 500

@app.route('/admin/promotion/add', methods=['GET', 'POST'])
def admin_add_promotion():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    
    connection = create_connection()
    if not connection:
        flash("Database connection error")
        return redirect(url_for('admin_promotions'))
    
    cursor = connection.cursor(dictionary=True)
    
    # Get restaurants for checkboxes
    cursor.execute("SELECT restaurant_id, name FROM Restaurants WHERE is_active = TRUE ORDER BY name")
    restaurants = cursor.fetchall()
    
    if request.method == 'POST':
        code = request.form['code']
        description = request.form['description']
        discount_percentage = request.form.get('discount_percentage') or None
        discount_amount = request.form.get('discount_amount') or None
        min_order_value = request.form.get('min_order_value') or None
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        is_active = 'is_active' in request.form
        restaurant_ids = request.form.getlist('restaurants')
        
        try:
            cursor.execute("""
                INSERT INTO Promotions (code, description, discount_percentage, discount_amount, 
                                       min_order_value, start_date, end_date, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (code, description, discount_percentage, discount_amount, 
                  min_order_value, start_date, end_date, is_active))
            
            promo_id = cursor.lastrowid
            
            # Add restaurant-promotion relationships
            for restaurant_id in restaurant_ids:
                cursor.execute("""
                    INSERT INTO RestaurantPromotions (restaurant_id, promo_id)
                    VALUES (%s, %s)
                """, (restaurant_id, promo_id))
            
            connection.commit()
            flash("Promotion added successfully!")
            return redirect(url_for('admin_promotions'))
        except Error as e:
            connection.rollback()
            print(f"Database error: {e}")
            flash("Error adding promotion. Please try again.")
        finally:
            cursor.close()
            connection.close()
    
    return render_template('admin_add_promotion.html', restaurants=restaurants)

if __name__ == '__main__':
    app.run(debug=True)
