CREATE DATABASE IF NOT EXISTS rentez;
USE rentez;


/* =========================================================
   1. USERS
========================================================= */

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    phone VARCHAR(15) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,

    user_type ENUM(
        'Customer',
        'Business',
        'Admin'
    ) DEFAULT 'Customer',

    delivery_address VARCHAR(255) NULL,
    delivery_city VARCHAR(100) NULL,
    delivery_state VARCHAR(100) NULL,
    delivery_pincode VARCHAR(6) NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


/* =========================================================
   2. BUSINESSES
========================================================= */

CREATE TABLE businesses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,

    business_name VARCHAR(150) NOT NULL,
    business_email VARCHAR(100) NOT NULL,
    business_phone VARCHAR(15) NOT NULL,
    registration_number VARCHAR(100) NOT NULL,

    address VARCHAR(255) NOT NULL,
    city VARCHAR(100) NOT NULL,
    description TEXT,

    approval_status ENUM(
        'Pending',
        'Approved',
        'Rejected'
    ) DEFAULT 'Pending',

    rejection_reason TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE,

    UNIQUE KEY unique_registration_number (registration_number),

    INDEX (user_id),
    INDEX (approval_status)
);


/* =========================================================
   3. BUSINESS DOCUMENTS
========================================================= */

CREATE TABLE business_documents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    business_id INT NOT NULL,

    document_type VARCHAR(100) NOT NULL,
    document_path VARCHAR(255) NOT NULL,

    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (business_id)
        REFERENCES businesses(id)
        ON DELETE CASCADE,

    INDEX (business_id)
);


/* =========================================================
   4. EQUIPMENT
========================================================= */

CREATE TABLE equipment (
    id INT AUTO_INCREMENT PRIMARY KEY,
    business_id INT NOT NULL,

    name VARCHAR(150) NOT NULL,
    category VARCHAR(100) NOT NULL,
    description TEXT,

    price_per_day DECIMAL(10,2) NOT NULL,
    image VARCHAR(255),

    available BOOLEAN DEFAULT TRUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    total_quantity INT NOT NULL DEFAULT 1,
    available_quantity INT NOT NULL DEFAULT 1,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (business_id)
        REFERENCES businesses(id),

    INDEX (business_id)
);


/* =========================================================
   5. PACKAGES
========================================================= */

CREATE TABLE packages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    business_id INT NOT NULL,

    name VARCHAR(150) NOT NULL,
    description TEXT,
    image VARCHAR(255),

    price_per_day DECIMAL(10,2) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (business_id)
        REFERENCES businesses(id)
        ON DELETE CASCADE,

    INDEX (business_id),
    INDEX (is_active)
);


/* =========================================================
   6. PACKAGE ITEMS
========================================================= */

CREATE TABLE package_items (
    id INT AUTO_INCREMENT PRIMARY KEY,

    package_id INT NOT NULL,
    equipment_id INT NOT NULL,
    quantity INT NOT NULL,

    FOREIGN KEY (package_id)
        REFERENCES packages(id)
        ON DELETE CASCADE,

    FOREIGN KEY (equipment_id)
        REFERENCES equipment(id),

    UNIQUE KEY unique_package_equipment (
        package_id,
        equipment_id
    ),

    INDEX (package_id),
    INDEX (equipment_id)
);


/* =========================================================
   7. ORDERS
========================================================= */

CREATE TABLE orders (
    id INT AUTO_INCREMENT PRIMARY KEY,

    user_id INT NOT NULL,

    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    total_days INT NOT NULL,

    subtotal DECIMAL(10,2) NOT NULL,
    delivery_fee DECIMAL(10,2) NOT NULL DEFAULT 0,
    total_amount DECIMAL(10,2) NOT NULL,

    delivery_address VARCHAR(255) NOT NULL,
    delivery_city VARCHAR(100) NOT NULL,
    delivery_state VARCHAR(100) NOT NULL,
    delivery_pincode VARCHAR(6) NOT NULL,

    order_status ENUM(
        'Pending',
        'Confirmed',
        'Cancelled',
        'Completed'
    ) DEFAULT 'Pending',

    payment_status ENUM(
        'Pending',
        'Paid',
        'Failed',
        'Cancelled',
        'Refund Pending',
        'Refunded',
        'Refund Failed'
    ) DEFAULT 'Pending',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE,

    INDEX (user_id),
    INDEX (order_status),
    INDEX (payment_status)
);


/* =========================================================
   8. ORDER ITEMS
========================================================= */

CREATE TABLE order_items (
    id INT AUTO_INCREMENT PRIMARY KEY,

    order_id INT NOT NULL,

    equipment_id INT NULL,
    package_id INT NULL,

    item_type ENUM(
        'Equipment',
        'Package'
    ) NOT NULL,

    item_name VARCHAR(150) NOT NULL,

    quantity INT NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,

    business_id INT NOT NULL,

    FOREIGN KEY (order_id)
        REFERENCES orders(id)
        ON DELETE CASCADE,

    FOREIGN KEY (equipment_id)
        REFERENCES equipment(id),

    FOREIGN KEY (package_id)
        REFERENCES packages(id),

    FOREIGN KEY (business_id)
        REFERENCES businesses(id),

    INDEX (order_id),
    INDEX (equipment_id),
    INDEX (package_id),
    INDEX (business_id)
);


/* =========================================================
   9. BOOKINGS
========================================================= */

CREATE TABLE bookings (
    id INT AUTO_INCREMENT PRIMARY KEY,

    user_id INT NOT NULL,

    equipment_id INT NULL,
    package_id INT NULL,
    order_id INT NULL,

    quantity INT NOT NULL DEFAULT 1,

    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    total_days INT NOT NULL,

    daily_rate DECIMAL(10,2) NOT NULL,
    total_amount DECIMAL(10,2) NOT NULL,

    delivery_address VARCHAR(255) NULL,
    delivery_city VARCHAR(100) NULL,
    delivery_state VARCHAR(100) NULL,
    delivery_pincode VARCHAR(6) NULL,

    booking_status ENUM(
        'Pending',
        'Confirmed',
        'Out for Delivery',
        'Delivered',
        'Returned',
        'Cancelled',
        'Completed'
    ) DEFAULT 'Pending',

    cancelled_by ENUM(
        'Customer',
        'Business',
        'Admin'
    ) NULL,

    cancellation_reason TEXT NULL,

    payment_status ENUM(
        'Pending',
        'Paid',
        'Failed',
        'Cancelled',
        'Refund Pending',
        'Refunded',
        'Refund Failed'
    ) DEFAULT 'Pending',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_booking_user
        FOREIGN KEY (user_id)
        REFERENCES users(id),

    CONSTRAINT fk_booking_equipment
        FOREIGN KEY (equipment_id)
        REFERENCES equipment(id),

    CONSTRAINT fk_booking_order
        FOREIGN KEY (order_id)
        REFERENCES orders(id)
        ON DELETE CASCADE,

    INDEX (user_id),
    INDEX (equipment_id),
    INDEX (order_id),
    INDEX (start_date),
    INDEX (end_date)
);


/* =========================================================
   10. BOOKING ITEMS
========================================================= */

CREATE TABLE booking_items (
    id INT AUTO_INCREMENT PRIMARY KEY,

    booking_id INT NOT NULL,
    equipment_id INT NOT NULL,

    quantity INT NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,

    item_name VARCHAR(150) NOT NULL,

    source ENUM(
        'Equipment',
        'Package'
    ) NOT NULL DEFAULT 'Equipment',

    FOREIGN KEY (booking_id)
        REFERENCES bookings(id)
        ON DELETE CASCADE,

    FOREIGN KEY (equipment_id)
        REFERENCES equipment(id),

    INDEX (booking_id),
    INDEX (equipment_id)
);


/* =========================================================
   11. PAYMENTS
========================================================= */

CREATE TABLE payments (
    id INT AUTO_INCREMENT PRIMARY KEY,

    booking_id INT NULL,
    order_id INT NULL,

    gateway VARCHAR(50) NOT NULL,

    gateway_order_id VARCHAR(255),
    gateway_payment_id VARCHAR(255),
    gateway_refund_id VARCHAR(255) NULL,

    amount DECIMAL(10,2) NOT NULL,
    currency VARCHAR(10) DEFAULT 'INR',

    payment_status ENUM(
        'Pending',
        'Paid',
        'Failed',
        'Cancelled',
        'Refund Pending',
        'Refunded',
        'Refund Failed'
    ) DEFAULT 'Pending',

    paid_at DATETIME NULL,
    refund_initiated_at DATETIME NULL,
    refunded_at DATETIME NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX (booking_id),
    INDEX (order_id),
    INDEX (gateway_order_id),
    INDEX (gateway_payment_id),

    CONSTRAINT fk_payment_booking
        FOREIGN KEY (booking_id)
        REFERENCES bookings(id),

    CONSTRAINT fk_payment_order
        FOREIGN KEY (order_id)
        REFERENCES orders(id)
        ON DELETE CASCADE
);


/* =========================================================
   12. PAYOUTS
========================================================= */

CREATE TABLE payouts (
    id INT AUTO_INCREMENT PRIMARY KEY,

    booking_id INT NOT NULL UNIQUE,
    business_id INT NOT NULL,

    amount DECIMAL(10,2) NOT NULL,
    gross_amount DECIMAL(10,2) NULL,
    commission_amount DECIMAL(10,2) NULL,

    currency VARCHAR(10) DEFAULT 'INR',

    payout_status ENUM(
        'Held',
        'Released',
        'Cancelled'
    ) DEFAULT 'Held',

    payout_reference VARCHAR(255) NULL,
    eligible_at DATETIME NULL,
    paid_at DATETIME NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX (business_id),
    INDEX (booking_id),
    INDEX (payout_status),

    CONSTRAINT fk_payout_booking
        FOREIGN KEY (booking_id)
        REFERENCES bookings(id),

    CONSTRAINT fk_payout_business
        FOREIGN KEY (business_id)
        REFERENCES businesses(id)
);


/* =========================================================
   13. PAYMENT REFUNDS
========================================================= */

CREATE TABLE payment_refunds (
    id INT AUTO_INCREMENT PRIMARY KEY,

    payment_id INT NOT NULL,
    order_id INT NOT NULL,
    booking_id INT NULL,

    refund_type ENUM(
        'Full',
        'Partial'
    ) NOT NULL,

    amount DECIMAL(10,2) NOT NULL,

    gateway_refund_id VARCHAR(255) NOT NULL UNIQUE,

    status ENUM(
        'Pending',
        'Processed',
        'Failed'
    ) NOT NULL DEFAULT 'Pending',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at DATETIME NULL,

    FOREIGN KEY (payment_id)
        REFERENCES payments(id)
        ON DELETE CASCADE,

    FOREIGN KEY (order_id)
        REFERENCES orders(id)
        ON DELETE CASCADE,

    FOREIGN KEY (booking_id)
        REFERENCES bookings(id)
        ON DELETE CASCADE,

    INDEX (payment_id),
    INDEX (order_id),
    INDEX (booking_id),
    INDEX (status)
);


/* =========================================================
   14. WISHLIST
========================================================= */

CREATE TABLE wishlist (
    id INT AUTO_INCREMENT PRIMARY KEY,

    user_id INT NOT NULL,
    equipment_id INT NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY unique_wishlist_item (
        user_id,
        equipment_id
    ),

    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE,

    FOREIGN KEY (equipment_id)
        REFERENCES equipment(id)
        ON DELETE CASCADE,

    INDEX (user_id),
    INDEX (equipment_id)
);


/* =========================================================
   15. BUSINESS VERIFICATION AUDIT
========================================================= */

CREATE TABLE business_verification_audit (
    id INT AUTO_INCREMENT PRIMARY KEY,

    business_id INT NOT NULL,
    admin_user_id INT NOT NULL,

    old_status ENUM(
        'Pending',
        'Approved',
        'Rejected'
    ) NOT NULL,

    new_status ENUM(
        'Approved',
        'Rejected'
    ) NOT NULL,

    rejection_reason TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (business_id)
        REFERENCES businesses(id)
        ON DELETE CASCADE,

    FOREIGN KEY (admin_user_id)
        REFERENCES users(id)
        ON DELETE CASCADE,

    INDEX (business_id),
    INDEX (admin_user_id),
    INDEX (created_at)
);


/* =========================================================
   16. NOTIFICATIONS
========================================================= */

CREATE TABLE notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,

    user_id INT NOT NULL,

    notification_type VARCHAR(50) NOT NULL,
    title VARCHAR(150) NOT NULL,
    message TEXT NOT NULL,
    link VARCHAR(255),

    is_read BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE,

    INDEX idx_notifications_user (user_id),
    INDEX idx_notifications_read (is_read),
    INDEX idx_notifications_created (created_at)
);


/* =========================================================
   17. PASSWORD RESET TOKENS
========================================================= */

CREATE TABLE password_reset_tokens (
    id INT AUTO_INCREMENT PRIMARY KEY,

    user_id INT NOT NULL,

    token_hash CHAR(64) NOT NULL UNIQUE,

    expires_at DATETIME NOT NULL,
    used_at DATETIME NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE,

    INDEX (user_id),
    INDEX (expires_at)
);


/* =========================================================
   LEGACY BOOKING-ITEM BACKFILL
   ---------------------------------------------------------
   Retained so older booking records can be converted into
   booking_items if this SQL file is used on an existing DB.
========================================================= */

INSERT INTO booking_items (
    booking_id,
    equipment_id,
    quantity,
    unit_price,
    item_name,
    source
)
SELECT
    b.id,
    b.equipment_id,
    b.quantity,
    b.daily_rate,
    e.name,
    'Equipment'
FROM bookings b
JOIN equipment e
    ON e.id = b.equipment_id
WHERE b.equipment_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
      FROM booking_items bi
      WHERE bi.booking_id = b.id
  );



/* =========================================================
   TEST TRANSACTION DATA RESET
   ---------------------------------------------------------
   RUN THIS ONLY WHEN YOU WANT TO CLEAR TEST TRANSACTIONS.

   PRESERVED:
   - users
   - businesses
   - business_documents
   - equipment
   - packages
   - package_items
   - wishlist
   - notifications
   - password_reset_tokens
   - business_verification_audit

   RESET:
   - orders
   - order_items
   - bookings
   - booking_items
   - payments
   - payment_refunds
   - payouts
========================================================= */

SET SQL_SAFE_UPDATES = 0;
SET FOREIGN_KEY_CHECKS = 0;

TRUNCATE TABLE payment_refunds;
TRUNCATE TABLE booking_items;
TRUNCATE TABLE order_items;
TRUNCATE TABLE payouts;
TRUNCATE TABLE payments;
TRUNCATE TABLE bookings;
TRUNCATE TABLE orders;

SET FOREIGN_KEY_CHECKS = 1;

UPDATE equipment
SET
    available_quantity = total_quantity,
    available = CASE
        WHEN total_quantity > 0 THEN 1
        ELSE 0
    END;

SET SQL_SAFE_UPDATES = 1; 

