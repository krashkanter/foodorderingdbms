-- Database Schema for Single Restaurant Food Ordering System
DROP DATABASE IF EXISTS food_ordering_db;
CREATE DATABASE food_ordering_db;
USE food_ordering_db;

-- Users table to store customer information
CREATE TABLE Users (
    user_id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,  -- Store hashed passwords
    email VARCHAR(100) NOT NULL UNIQUE,
    phone VARCHAR(15),
    is_admin BOOLEAN DEFAULT FALSE,  -- Flag to identify admin users
    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Dishes table (menu items)
CREATE TABLE Dishes (
    dish_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    price DECIMAL(10,2) NOT NULL,
    is_vegetarian BOOLEAN DEFAULT FALSE,
    is_available BOOLEAN DEFAULT TRUE,
    category VARCHAR(50)  -- e.g., 'Appetizer', 'Main Course', 'Dessert'
);

-- Orders table
CREATE TABLE Orders (
    order_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    delivery_address TEXT NOT NULL,  -- Address is included with each order
    total_amount DECIMAL(10,2) NOT NULL,
    status ENUM('Pending', 'Confirmed', 'Preparing', 'Ready for Pickup', 'Out for Delivery', 'Delivered', 'Rejected', 'Cancelled') DEFAULT 'Pending',
    payment_method ENUM('Credit Card', 'Debit Card', 'Cash on Delivery', 'Digital Wallet') NOT NULL,
    payment_status BOOLEAN DEFAULT FALSE,
    rejection_reason TEXT,  -- Only filled if order is rejected
    FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE RESTRICT
);

-- Order Items table (for dishes in each order)
CREATE TABLE OrderItems (
    order_item_id INT PRIMARY KEY AUTO_INCREMENT,
    order_id INT NOT NULL,
    dish_id INT NOT NULL,
    quantity INT NOT NULL,
    item_price DECIMAL(10,2) NOT NULL,  -- Price at the time of ordering
    special_instructions TEXT,
    FOREIGN KEY (order_id) REFERENCES Orders(order_id) ON DELETE CASCADE,
    FOREIGN KEY (dish_id) REFERENCES Dishes(dish_id) ON DELETE RESTRICT
);

-- Reviews table
CREATE TABLE Reviews (
    review_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    order_id INT,
    rating INT NOT NULL CHECK (rating >= 1 AND rating <= 5),
    comment TEXT,
    review_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (order_id) REFERENCES Orders(order_id) ON DELETE SET NULL
);

-- Indexes for performance optimization
CREATE INDEX idx_orders_user ON Orders(user_id);
CREATE INDEX idx_order_items_order ON OrderItems(order_id);