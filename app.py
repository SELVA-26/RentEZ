from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    jsonify,
    send_from_directory,
    flash
)
from flask_mysqldb import MySQL
import os
import re
import uuid
import secrets
import threading
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import razorpay
import hmac
import hashlib
import smtplib
from email.message import EmailMessage

from dotenv import load_dotenv
load_dotenv()

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

razorpay_client = razorpay.Client(
    auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)
)

# =========================
# RENTEZ PLATFORM COMMISSION
# =========================

PLATFORM_COMMISSION_RATE = 0.10


# =========================
# EMAIL CONFIGURATION
# =========================

SMTP_HOST = os.getenv(
    "SMTP_HOST",
    "smtp.gmail.com"
)

SMTP_PORT = int(
    os.getenv(
        "SMTP_PORT",
        "587"
    )
)

SMTP_USERNAME = os.getenv(
    "SMTP_USERNAME"
)

SMTP_PASSWORD = os.getenv(
    "SMTP_PASSWORD"
)

SMTP_FROM = os.getenv(
    "SMTP_FROM",
    SMTP_USERNAME
)

CONTACT_EMAIL = os.getenv(
    "CONTACT_EMAIL",
    "selvathevar2601@gmail.com"
)

# =========================
# FLASK APP
# =========================

app = Flask(__name__)

# Flask session security
# Uses SECRET_KEY from environment when available.
# A random fallback prevents a hardcoded secret from being exposed.
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

if not app.config["SECRET_KEY"]:
    raise RuntimeError(
        "SECRET_KEY is not configured. "
        "Add SECRET_KEY to the .env file."
    )
    
# Keep users logged in for 90 days
app.permanent_session_lifetime = timedelta(days=90)

# Session security
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# HTTPS deployments should set SESSION_COOKIE_SECURE=true.
# Local HTTP development remains supported by default.
app.config["SESSION_COOKIE_SECURE"] = (
    os.getenv(
        "SESSION_COOKIE_SECURE",
        "false"
    ).lower() == "true"
)

app.config["SESSION_COOKIE_PATH"] = "/"

# =========================================================
# CSRF PROTECTION
# =========================================================

CSRF_EXEMPT_ENDPOINTS = {
    "razorpay_webhook"
}


def get_csrf_token():

    token = session.get("csrf_token")

    if not token:

        token = secrets.token_urlsafe(32)

        session["csrf_token"] = token

    return token


app.jinja_env.globals["csrf_token"] = get_csrf_token


@app.before_request
def csrf_protect():

    if request.method != "POST":
        return None

    # Razorpay calls this endpoint directly.
    # It cannot provide our browser session CSRF token.
    if request.endpoint in CSRF_EXEMPT_ENDPOINTS:
        return None

    session_token = session.get("csrf_token")

    if not session_token:
        return csrf_failure()

    submitted_token = (
        request.form.get("csrf_token")
        or request.headers.get("X-CSRFToken")
        or request.headers.get("X-CSRF-Token")
    )

    if not submitted_token:

        return csrf_failure()

    if not hmac.compare_digest(
        str(session_token),
        str(submitted_token)
    ):
        return csrf_failure()

    return None


def csrf_failure():

    if request.is_json:

        return jsonify({
            "success": False,
            "message": "Security validation failed. Please refresh the page and try again."
        }), 403

    return (
        "Security validation failed. "
        "Please refresh the page and try again.",
        403
    )
    
    
# =========================================================
# NOTIFICATION HELPERS
# =========================================================

def create_notification(
    user_id,
    notification_type,
    title,
    message,
    link=None
):

    cursor = mysql.connection.cursor()

    try:

        cursor.execute("""
            INSERT INTO notifications
            (
                user_id,
                notification_type,
                title,
                message,
                link
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s
            )
        """, (
            user_id,
            notification_type,
            title,
            message,
            link
        ))

    finally:
        cursor.close()


def send_email(
    recipient,
    subject,
    body
):

    if not recipient:
        return False

    if not SMTP_USERNAME or not SMTP_PASSWORD:

        print(
            "SMTP is not configured. "
            f"Skipping email to {recipient}."
        )

        return False

    try:

        email = EmailMessage()

        email["Subject"] = subject
        email["From"] = SMTP_FROM
        email["To"] = recipient

        email.set_content(body)

        with smtplib.SMTP(
            SMTP_HOST,
            SMTP_PORT,
            timeout=15
        ) as server:

            server.starttls()

            server.login(
                SMTP_USERNAME,
                SMTP_PASSWORD
            )

            server.send_message(email)

        return True

    except Exception as e:

        print(
            "Email sending failed:",
            e
        )

        return False


# =========================================================
# NOTIFICATIONS AVAILABLE TO TEMPLATES
# =========================================================

@app.context_processor
def notification_context():

    user_id = session.get("user_id")

    if not user_id:

        return {
            "notifications": [],
            "unread_notification_count": 0,
        }

    cursor = mysql.connection.cursor()

    try:

        cursor.execute("""
            SELECT
                id,
                notification_type,
                title,
                message,
                link,
                is_read,
                created_at
            FROM notifications
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 8
        """, (
            user_id,
        ))

        notifications = cursor.fetchall()


        cursor.execute("""
            SELECT COUNT(*)
            FROM notifications
            WHERE user_id = %s
              AND is_read = FALSE
        """, (
            user_id,
        ))

        unread_count = (
            cursor.fetchone()[0] or 0
        )


        return {
            "notifications": notifications,
            "unread_notification_count":
                unread_count,
        }

    finally:
        cursor.close()


# =========================================================
# MARK ONE NOTIFICATION READ
# =========================================================

@app.route(
    "/notifications/read/<int:notification_id>",
    methods=["POST"]
)
def mark_notification_read(notification_id):

    if "user_id" not in session:

        return jsonify({
            "success": False,
            "message": "Please login again."
        }), 401


    cursor = mysql.connection.cursor()

    try:

        cursor.execute("""
            UPDATE notifications
            SET is_read = TRUE
            WHERE id = %s
              AND user_id = %s
        """, (
            notification_id,
            session["user_id"]
        ))

        mysql.connection.commit()

        return jsonify({
            "success": True
        })

    except Exception as e:

        mysql.connection.rollback()

        print(
            "Notification read error:",
            e
        )

        return jsonify({
            "success": False
        }), 500

    finally:
        cursor.close()


# =========================================================
# MARK ALL NOTIFICATIONS READ
# =========================================================

@app.route(
    "/notifications/mark-all-read",
    methods=["POST"]
)
def mark_all_notifications_read():

    if "user_id" not in session:

        return jsonify({
            "success": False
        }), 401


    cursor = mysql.connection.cursor()

    try:

        cursor.execute("""
            UPDATE notifications
            SET is_read = TRUE
            WHERE user_id = %s
              AND is_read = FALSE
        """, (
            session["user_id"],
        ))

        mysql.connection.commit()

        return jsonify({
            "success": True
        })

    except Exception as e:

        mysql.connection.rollback()

        return jsonify({
            "success": False
        }), 500

    finally:
        cursor.close()


# =========================================================
# CART HELPERS
# =========================================================

def get_cart():

    cart = session.get("cart")

    if not isinstance(cart, dict):

        cart = {
            "start_date": None,
            "end_date": None,
            "items": []
        }

    if "start_date" not in cart:
        cart["start_date"] = None

    if "end_date" not in cart:
        cart["end_date"] = None

    if "items" not in cart:
        cart["items"] = []

    return cart


def save_cart(cart):

    session["cart"] = cart

    session.modified = True


def clear_cart():

    session.pop(
        "cart",
        None
    )

    session.modified = True


def cart_item_key(item_type, item_id):

    return f"{item_type}:{item_id}"


def get_cart_count():

    cart = get_cart()

    return sum(
        int(item.get("quantity", 0))
        for item in cart["items"]
    )
    
@app.context_processor
def inject_cart_data():

    if session.get("user_id"):

        return {
            "cart_count": get_cart_count()
        }

    return {
        "cart_count": 0
    }

# =========================
# MYSQL CONFIGURATION
# =========================

app.config["MYSQL_HOST"] = os.getenv("MYSQL_HOST")
app.config["MYSQL_USER"] = os.getenv("MYSQL_USER")
app.config["MYSQL_PASSWORD"] = os.getenv("MYSQL_PASSWORD")
app.config["MYSQL_DB"] = os.getenv("MYSQL_DB")


mysql = MySQL(app)


def customer_logged_in():
    return (
        "user_id" in session
        and session.get("user_type") == "Customer"
    )

# =========================================================
# CUSTOMER ROUTE AUTHORIZATION
# =========================================================

CUSTOMER_ENDPOINTS = {
    "dashboard",
    "equipment",
    "equipment_details",
    "check_availability",
    "rent_equipment",
    "payment",
    "cancel_booking",
    "my_rentals",
    "wishlist",
    "toggle_wishlist",
    "packages",
    "package_details",
    "check_package_availability",
    "checkout",
    "create_order",
    "order_payment",
    "order_payment_success",
    "order_payment_failed",
    "order_success",
}

CUSTOMER_API_ENDPOINTS = {
    "check_availability",
    "payment_success",
    "check_package_availability",
    "order_payment_success",
    "order_payment_failed",
}


@app.before_request
def customer_authorization():

    if request.endpoint not in CUSTOMER_ENDPOINTS:
        return None

    if customer_logged_in():
        return None

    # API/AJAX customer endpoints return JSON
    if request.endpoint in CUSTOMER_API_ENDPOINTS:
        return jsonify({
            "success": False,
            "message": "Please login as a customer."
        }), 401

    # Normal customer pages redirect to customer login
    return redirect(url_for("login"))


# =========================================================
# BUSINESS APPROVAL AUTHORIZATION
# =========================================================

BUSINESS_APPROVAL_REQUIRED_ENDPOINTS = {
    "business_dashboard",
    "business_bookings",
    "update_booking_status",
    "edit_equipment",
    "business_cancel_booking",
    "delete_equipment",
    "toggle_equipment",
    "add_equipment",
    "business_packages",
    "create_business_package",
    "edit_business_package",
    "toggle_business_package",
    "business_equipment",
}


@app.before_request
def business_approval_authorization():

    if request.endpoint not in BUSINESS_APPROVAL_REQUIRED_ENDPOINTS:
        return None

    if (
        "user_id" not in session
        or session.get("user_type") != "Business"
        or "business_id" not in session
    ):
        return redirect(url_for("business_login"))

    cursor = mysql.connection.cursor()

    try:

        cursor.execute("""
            SELECT approval_status
            FROM businesses
            WHERE id = %s
              AND user_id = %s
        """, (
            session["business_id"],
            session["user_id"]
        ))

        business = cursor.fetchone()

    finally:
        cursor.close()

    if not business:
        session.clear()
        return redirect(url_for("business_login"))

    if business[0] != "Approved":
        return redirect(url_for("business_status"))

    return None

# =========================
# EQUIPMENT UPLOAD FOLDER
# =========================

EQUIPMENT_UPLOAD_FOLDER = os.path.join(
    app.root_path,
    "uploads",
    "equipment"
)

os.makedirs(
    EQUIPMENT_UPLOAD_FOLDER,
    exist_ok=True
)


# =========================
# EQUIPMENT IMAGE ROUTE
# =========================

@app.route("/equipment-image/<path:filename>")
def equipment_image(filename):

    return send_from_directory(
        EQUIPMENT_UPLOAD_FOLDER,
        filename
    )
    
    
@app.route("/")
def home():

    cursor = mysql.connection.cursor()

    try:

        # =================================================
        # FEATURED EQUIPMENT
        # =================================================

        cursor.execute("""
            SELECT
                id,
                name,
                category,
                description,
                price_per_day,
                image,
                available
            FROM equipment
            WHERE is_active = TRUE
            ORDER BY created_at DESC
            LIMIT 12
        """)

        equipment_list = cursor.fetchall()


        # =================================================
        # FEATURED BUSINESSES
        # =================================================

        cursor.execute("""
            SELECT
                b.id,
                b.business_name,
                b.city,
                COUNT(e.id) AS equipment_count
            FROM businesses b
            LEFT JOIN equipment e
                ON e.business_id = b.id
               AND e.is_active = TRUE
            WHERE b.approval_status = 'Approved'
            GROUP BY
                b.id,
                b.business_name,
                b.city
            ORDER BY equipment_count DESC
            LIMIT 6
        """)

        business_list = cursor.fetchall()


        # =================================================
        # LIVE PLATFORM STATS
        # =================================================

        cursor.execute("""
            SELECT COUNT(*)
            FROM businesses
            WHERE approval_status = 'Approved'
        """)

        verified_businesses = (
            cursor.fetchone()[0] or 0
        )


        cursor.execute("""
            SELECT COUNT(*)
            FROM equipment
            WHERE is_active = TRUE
        """)

        equipment_count = (
            cursor.fetchone()[0] or 0
        )


        cursor.execute("""
            SELECT COUNT(DISTINCT city)
            FROM businesses
            WHERE approval_status = 'Approved'
        """)

        cities_count = (
            cursor.fetchone()[0] or 0
        )


        cursor.execute("""
            SELECT COUNT(*)
            FROM bookings
            WHERE booking_status = 'Completed'
        """)

        successful_rentals = (
            cursor.fetchone()[0] or 0
        )

        cursor.execute("""
            SELECT
                p.id,
                p.name,
                p.description,
                p.image,
                p.price_per_day,
                b.business_name,
                b.city,
                COUNT(pi.id)
            FROM packages p
            JOIN businesses b
                ON b.id = p.business_id
            LEFT JOIN package_items pi
                ON pi.package_id = p.id
            WHERE p.is_active = TRUE
            AND b.approval_status = 'Approved'
            AND NOT EXISTS (
                    SELECT 1
                    FROM package_items pi2
                    JOIN equipment e2
                        ON e2.id = pi2.equipment_id
                    WHERE pi2.package_id = p.id
                    AND e2.is_active = FALSE
            )
            GROUP BY
                p.id,
                p.name,
                p.description,
                p.image,
                p.price_per_day,
                b.business_name,
                b.city
            ORDER BY p.created_at DESC
            LIMIT 6
        """)

        package_list = cursor.fetchall()

        return render_template(
            "index.html",
            equipment_list=equipment_list,
            business_list=business_list,
            verified_businesses=verified_businesses,
            equipment_count=equipment_count,
            cities_count=cities_count,
            successful_rentals=successful_rentals,
            package_list=package_list,
        )

    finally:

        cursor.close()
    

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        if not email or not password:

            return render_template(
                "login.html",
                login_error="Please enter your email and password."
            )

        cursor = mysql.connection.cursor()

        try:

            cursor.execute(
                """
                SELECT *
                FROM users
                WHERE email = %s
                  AND user_type = 'Customer'
                """,
                (email,)
            )

            user = cursor.fetchone()

            if user:

                user_id = user[0]
                stored_password = user[4]

                if check_password_hash(
                    stored_password,
                    password
                ):

                    # Commit automatic bcrypt -> Werkzeug migration
                    mysql.connection.commit()

                    session.clear()

                    session.permanent = True

                    session["user_id"] = user_id
                    session["user_name"] = user[1].split()[0]
                    session["user_type"] = "Customer"

                    return redirect(
                        url_for("home")
                    )

            return render_template(
                "login.html",
                login_error="Invalid email or password"
            )

        except Exception as e:

            mysql.connection.rollback()

            print(
                "Customer login error:",
                e
            )

            return render_template(
                "login.html",
                login_error=(
                    "Unable to log in right now. "
                    "Please try again."
                )
            )

        finally:
            cursor.close()

    return render_template("login.html")


@app.route("/dashboard")
def dashboard():

    if not customer_logged_in():
        return redirect(url_for("login"))

    user_id = session["user_id"]

    cursor = mysql.connection.cursor()

    try:

        # =====================================================
        # EQUIPMENT
        # =====================================================

        cursor.execute("""
            SELECT
                id,
                name,
                category,
                description,
                price_per_day,
                image,
                available
            FROM equipment
            WHERE is_active = TRUE
            ORDER BY created_at DESC
        """)

        equipment_list = cursor.fetchall()


        # =====================================================
        # DASHBOARD STATISTICS
        # =====================================================

        cursor.execute("""
            SELECT COUNT(*)
            FROM bookings
            WHERE user_id = %s
              AND booking_status = 'Delivered'
        """, (user_id,))

        active_rentals = cursor.fetchone()[0] or 0


        cursor.execute("""
            SELECT COUNT(*)
            FROM bookings
            WHERE user_id = %s
              AND booking_status IN (
                  'Confirmed',
                  'Out for Delivery'
              )
        """, (user_id,))

        upcoming_bookings = cursor.fetchone()[0] or 0

        cursor.execute("""
            SELECT COUNT(*)
            FROM wishlist w
            JOIN equipment e
                ON w.equipment_id = e.id
            WHERE w.user_id = %s
            AND e.is_active = TRUE
        """, (
            user_id,
        ))

        wishlist_count = cursor.fetchone()[0] or 0
        
        
        cursor.execute("""
            SELECT COUNT(*)
            FROM bookings
            WHERE user_id = %s
              AND booking_status != 'Cancelled'
        """, (user_id,))

        total_rentals = cursor.fetchone()[0] or 0


        # =====================================================
        # RECENT RENTALS
        # =====================================================

        cursor.execute("""
            SELECT
                b.id,
                b.start_date,
                b.end_date,
                b.total_days,
                b.daily_rate,
                b.total_amount,
                b.booking_status,
                b.payment_status,
                e.id,
                COALESCE(
                e.name,
                pkg.name
            ) AS name,
                CASE
                    WHEN b.package_id IS NOT NULL
                    THEN 'Rental Package'
                    ELSE e.category
                END AS category,
                COALESCE(
                    e.image,
                    pkg.image
                ) AS image,
                b.package_id
            FROM bookings b
            LEFT JOIN equipment e
                ON b.equipment_id = e.id

            LEFT JOIN packages pkg
                ON b.package_id = pkg.id
            WHERE b.user_id = %s
            ORDER BY b.created_at DESC
            LIMIT 4
        """, (user_id,))

        recent_rentals = cursor.fetchall()
        cart_count = get_cart_count()
        return render_template(
            "dashboard.html",
            user_name=session["user_name"],
            equipment_list=equipment_list,
            active_rentals=active_rentals,
            upcoming_bookings=upcoming_bookings,
            total_rentals=total_rentals,
            recent_rentals=recent_rentals,
            wishlist_count=wishlist_count,
            cart_count=cart_count
        )

    except Exception as e:

        print("Customer dashboard error:", e)

        return (
            "Unable to load your dashboard right now.",
            500
        )

    finally:
        cursor.close()


@app.route("/logout", methods=["GET", "POST"])
def logout():

    session.clear()

    return redirect(url_for("home"))


@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        fullname = request.form.get("fullname", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        confirmPassword = request.form.get("confirmPassword", "")
        terms = request.form.get("terms")
        
        # -------------------------
        # BASIC VALIDATION
        # -------------------------

        # -------------------------
        # FULL NAME VALIDATION
        # -------------------------

        fullname = " ".join(
            fullname.split()
        )

        if not fullname:
            return render_template(
                "register.html",
                error_message="Please enter your full name."
            )

        if len(fullname) < 2 or len(fullname) > 100:
            return render_template(
                "register.html",
                error_message=(
                    "Full name must be between 2 and 100 characters."
                )
            )

        if not re.fullmatch(
            r"[A-Za-z][A-Za-z .'-]*[A-Za-z]",
            fullname
        ):
            return render_template(
                "register.html",
                error_message=(
                    "Full name can contain only letters, spaces, "
                    "apostrophes, dots and hyphens."
                )
            )

        # Make sure there are at least two actual letters.
        if sum(
            character.isalpha()
            for character in fullname
        ) < 2:
            return render_template(
                "register.html",
                error_message="Please enter a valid full name."
            )


        # -------------------------
        # EMAIL VALIDATION
        # -------------------------

        if not email:
            return render_template(
                "register.html",
                error_message="Please enter your email address."
            )


        # -------------------------
        # INDIAN PHONE VALIDATION
        # -------------------------

        if not re.fullmatch(
            r"[6-9][0-9]{9}",
            phone
        ):
            return render_template(
                "register.html",
                error_message=(
                    "Please enter a valid Indian mobile number "
                    "starting with 6, 7, 8 or 9."
                )
            )

        # Reject numbers such as 0000000000,
        # 1111111111, 9999999999, etc.
        if len(set(phone)) == 1:
            return render_template(
                "register.html",
                error_message=(
                    "Please enter a valid mobile number."
                )
            )

        if len(password) < 6:
            return render_template(
                "register.html",
                error_message="Password must be at least 6 characters long."
            )

        if password != confirmPassword:
            return render_template(
                "register.html",
                error_message="The passwords you entered do not match."
            )
        
        
        if terms != "on":
            return render_template(
                "register.html",
                error_message=(
                    "You must agree to the RentEZ Terms & Conditions "
                    "to create an account."
                )
            )
        cursor = mysql.connection.cursor()

        try:

            # -------------------------
            # DUPLICATE EMAIL
            # -------------------------

            cursor.execute("""
                SELECT id
                FROM users
                WHERE email = %s
                LIMIT 1
            """, (email,))

            if cursor.fetchone():

                return render_template(
                    "register.html",
                    error_message=(
                        "An account with this email address "
                        "already exists."
                    )
                )

            # -------------------------
            # DUPLICATE PHONE
            # -------------------------

            cursor.execute("""
                SELECT id
                FROM users
                WHERE phone = %s
                LIMIT 1
            """, (phone,))

            if cursor.fetchone():

                return render_template(
                    "register.html",
                    error_message=(
                        "An account with this phone number "
                        "already exists."
                    )
                )

            # -------------------------
            # CREATE CUSTOMER
            # -------------------------

            hashed_password = generate_password_hash(
                password
            )

            cursor.execute("""
                INSERT INTO users
                (
                    full_name,
                    email,
                    phone,
                    password,
                    user_type
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    'Customer'
                )
            """, (
                fullname,
                email,
                phone,
                hashed_password
            ))

            mysql.connection.commit()

            return redirect(
                url_for("login")
            )

        except Exception as e:

            mysql.connection.rollback()

            print(
                "Customer registration error:",
                e
            )

            return render_template(
                "register.html",
                error_message=(
                    "Unable to create your account right now. "
                    "Please try again."
                )
            )

        finally:
            cursor.close()

    return render_template(
        "register.html"
    )


# =========================================================
# CUSTOMER PROFILE
# =========================================================

@app.route("/profile", methods=["GET", "POST"])
def profile():

    if not customer_logged_in():
        return redirect(url_for("login"))

    user_id = session["user_id"]

    cursor = mysql.connection.cursor()

    try:

        cursor.execute("""
            SELECT
                id,
                full_name,
                email,
                phone,
                password,
                delivery_address,
                delivery_city,
                delivery_state,
                delivery_pincode
            FROM users
            WHERE id = %s
            AND user_type = 'Customer'
        """, (user_id,))

        user = cursor.fetchone()

        if not user:
            session.clear()
            return redirect(url_for("login"))

        # =================================================
        # PROFILE INFORMATION UPDATE
        # =================================================

        if request.method == "POST" and \
           request.form.get("form_type") == "profile":

            full_name = request.form.get(
                "full_name",
                ""
            ).strip()

            email = request.form.get(
                "email",
                ""
            ).strip().lower()

            phone = request.form.get(
                "phone",
                ""
            ).strip()

            delivery_address = request.form.get(
                "delivery_address",
                ""
            ).strip()

            delivery_city = request.form.get(
                "delivery_city",
                ""
            ).strip()

            delivery_state = request.form.get(
                "delivery_state",
                ""
            ).strip()

            delivery_pincode = request.form.get(
                "delivery_pincode",
                ""
            ).strip()
            
            if not full_name:
                return render_template(
                    "customer_profile.html",
                    user=user,
                    profile_error="Full name is required."
                )

            if len(full_name) < 2:
                return render_template(
                    "customer_profile.html",
                    user=user,
                    profile_error="Please enter a valid full name."
                )

            if not email or "@" not in email:
                return render_template(
                    "customer_profile.html",
                    user=user,
                    profile_error="Please enter a valid email address."
                )

            if not phone.isdigit() or len(phone) != 10:
                return render_template(
                    "customer_profile.html",
                    user=user,
                    profile_error="Please enter a valid 10-digit phone number."
                )

            # ---------------------------------------------
            # EMAIL DUPLICATE CHECK
            # ---------------------------------------------

            cursor.execute("""
                SELECT id
                FROM users
                WHERE email = %s
                  AND id <> %s
                LIMIT 1
            """, (
                email,
                user_id
            ))

            if cursor.fetchone():

                return render_template(
                    "customer_profile.html",
                    user=user,
                    profile_error=(
                        "This email address is already "
                        "associated with another account."
                    )
                )

            # ---------------------------------------------
            # PHONE DUPLICATE CHECK
            # ---------------------------------------------

            cursor.execute("""
                SELECT id
                FROM users
                WHERE phone = %s
                  AND id <> %s
                LIMIT 1
            """, (
                phone,
                user_id
            ))

            if cursor.fetchone():

                return render_template(
                    "customer_profile.html",
                    user=user,
                    profile_error=(
                        "This phone number is already "
                        "associated with another account."
                    )
                )

            cursor.execute("""
                UPDATE users
                SET
                    full_name = %s,
                    email = %s,
                    phone = %s,
                    delivery_address = %s,
                    delivery_city = %s,
                    delivery_state = %s,
                    delivery_pincode = %s
                WHERE id = %s
                AND user_type = 'Customer'
            """, (
                    full_name,
                    email,
                    phone,
                    delivery_address,
                    delivery_city,
                    delivery_state,
                    delivery_pincode,
                    user_id
                ))

            mysql.connection.commit()

            session["user_name"] = full_name.split()[0]

            cursor.execute("""
                SELECT
                    id,
                    full_name,
                    email,
                    phone,
                    password,
                    delivery_address,
                    delivery_city,
                    delivery_state,
                    delivery_pincode
                FROM users
                WHERE id = %s
                AND user_type = 'Customer'
            """, (user_id,))

            user = cursor.fetchone()

            return render_template(
                "customer_profile.html",
                user=user,
                profile_success="Profile updated successfully."
            )

        # =================================================
        # CHANGE PASSWORD
        # =================================================

        if request.method == "POST" and \
           request.form.get("form_type") == "password":

            current_password = request.form.get(
                "current_password",
                ""
            )

            new_password = request.form.get(
                "new_password",
                ""
            )

            confirm_password = request.form.get(
                "confirm_password",
                ""
            )

            if not current_password or \
               not new_password or \
               not confirm_password:

                return render_template(
                    "customer_profile.html",
                    user=user,
                    password_error=(
                        "Please fill in all password fields."
                    )
                )

            if len(new_password) < 6:

                return render_template(
                    "customer_profile.html",
                    user=user,
                    password_error=(
                        "New password must be at least "
                        "6 characters long."
                    )
                )

            if new_password != confirm_password:

                return render_template(
                    "customer_profile.html",
                    user=user,
                    password_error=(
                        "New passwords do not match."
                    )
                )

            if not check_password_hash(
                user[4],
                current_password
            ):

                return render_template(
                    "customer_profile.html",
                    user=user,
                    password_error=(
                        "Current password is incorrect."
                    )
                )

            if check_password_hash(
                user[4],
                new_password
            ):

                return render_template(
                    "customer_profile.html",
                    user=user,
                    password_error=(
                        "New password must be different "
                        "from your current password."
                    )
                )

            hashed_password = generate_password_hash(
                new_password
            )

            cursor.execute("""
                UPDATE users
                SET password = %s
                WHERE id = %s
                  AND user_type = 'Customer'
            """, (
                hashed_password,
                user_id
            ))

            # Invalidate outstanding reset tokens
            cursor.execute("""
                UPDATE password_reset_tokens
                SET used_at = NOW()
                WHERE user_id = %s
                  AND used_at IS NULL
            """, (user_id,))

            mysql.connection.commit()

            return render_template(
                "customer_profile.html",
                user=user,
                password_success=(
                    "Your password has been changed successfully."
                )
            )

        return render_template(
            "customer_profile.html",
            user=user
        )

    except Exception as e:

        mysql.connection.rollback()

        print(
            "Customer profile error:",
            e
        )

        return render_template(
            "customer_profile.html",
            user=user if "user" in locals() else None,
            profile_error=(
                "Unable to update your profile right now."
            )
        )

    finally:
        cursor.close()
        
        
# =========================================================
# FORGOT PASSWORD
# =========================================================

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        # Generic response prevents account enumeration
        generic_message = (
            "If an account exists with that email address, "
            "we have sent a password reset link."
        )

        if not email:

            return render_template(
                "forgot_password.html",
                reset_message=generic_message
            )

        cursor = mysql.connection.cursor()

        try:

            cursor.execute("""
                SELECT
                    id,
                    full_name,
                    email
                FROM users
                WHERE email = %s
                  AND user_type = 'Customer'
                LIMIT 1
            """, (email,))

            user = cursor.fetchone()

            if user:

                # Invalidate previous unused tokens
                cursor.execute("""
                    UPDATE password_reset_tokens
                    SET used_at = NOW()
                    WHERE user_id = %s
                      AND used_at IS NULL
                """, (user[0],))

                raw_token = secrets.token_urlsafe(48)

                token_hash = hashlib.sha256(
                    raw_token.encode("utf-8")
                ).hexdigest()

                cursor.execute("""
                    INSERT INTO password_reset_tokens
                    (
                        user_id,
                        token_hash,
                        expires_at
                    )
                    VALUES (
                        %s,
                        %s,
                        DATE_ADD(NOW(), INTERVAL 30 MINUTE)
                    )
                """, (
                    user[0],
                    token_hash
                ))

                mysql.connection.commit()

                reset_link = url_for(
                    "reset_password",
                    token=raw_token,
                    _external=True
                )

                send_email(
                    user[2],
                    "RentEZ Password Reset",
                    f"""Hello {user[1]},

We received a request to reset your RentEZ password.

Use the link below to create a new password:

{reset_link}

This link will expire in 30 minutes and can only be used once.

If you did not request this reset, you can safely ignore this email.

Regards,
RentEZ Team
"""
                )

            else:

                mysql.connection.commit()

            return render_template(
                "forgot_password.html",
                reset_message=generic_message
            )

        except Exception as e:

            mysql.connection.rollback()

            print(
                "Forgot password error:",
                e
            )

            return render_template(
                "forgot_password.html",
                reset_message=generic_message
            )

        finally:
            cursor.close()

    return render_template(
        "forgot_password.html"
    )


@app.route(
    "/reset-password/<token>",
    methods=["GET", "POST"]
)
def reset_password(token):

    token_hash = hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()

    cursor = mysql.connection.cursor()

    try:

        cursor.execute("""
            SELECT
                pr.id,
                pr.user_id,
                u.email
            FROM password_reset_tokens pr
            JOIN users u
                ON u.id = pr.user_id
            WHERE pr.token_hash = %s
              AND pr.used_at IS NULL
              AND pr.expires_at > NOW()
              AND u.user_type = 'Customer'
            LIMIT 1
        """, (token_hash,))

        reset_record = cursor.fetchone()

        if not reset_record:

            return render_template(
                "reset_password.html",
                invalid_token=True
            )

        if request.method == "POST":

            new_password = request.form.get(
                "new_password",
                ""
            )

            confirm_password = request.form.get(
                "confirm_password",
                ""
            )

            if len(new_password) < 6:

                return render_template(
                    "reset_password.html",
                    token=token,
                    reset_error=(
                        "New password must be at least "
                        "6 characters long."
                    )
                )

            if new_password != confirm_password:

                return render_template(
                    "reset_password.html",
                    token=token,
                    reset_error=(
                        "Passwords do not match."
                    )
                )

            hashed_password = generate_password_hash(
                new_password
            )

            cursor.execute("""
                UPDATE users
                SET password = %s
                WHERE id = %s
                  AND user_type = 'Customer'
            """, (
                hashed_password,
                reset_record[1]
            ))

            cursor.execute("""
                UPDATE password_reset_tokens
                SET used_at = NOW()
                WHERE id = %s
            """, (
                reset_record[0],
            ))

            # Invalidate any other reset links
            cursor.execute("""
                UPDATE password_reset_tokens
                SET used_at = NOW()
                WHERE user_id = %s
                  AND used_at IS NULL
            """, (
                reset_record[1],
            ))

            mysql.connection.commit()

            return render_template(
                "reset_password.html",
                reset_success=(
                    "Your password has been reset successfully. "
                    "You can now log in with your new password."
                )
            )

        return render_template(
            "reset_password.html",
            token=token
        )

    except Exception as e:

        mysql.connection.rollback()

        print(
            "Reset password error:",
            e
        )

        return render_template(
            "reset_password.html",
            reset_error=(
                "Unable to reset your password right now."
            )
        )

    finally:
        cursor.close()


# =====================================================
# UPLOAD FOLDERS
# =====================================================

UPLOAD_FOLDER = os.path.join(
    app.root_path,
    "uploads"
)

BUSINESS_DOCUMENT_FOLDER = os.path.join(
    UPLOAD_FOLDER,
    "business_documents"
)

EQUIPMENT_UPLOAD_FOLDER = os.path.join(
    UPLOAD_FOLDER,
    "equipment"
)


os.makedirs(
    BUSINESS_DOCUMENT_FOLDER,
    exist_ok=True
)

os.makedirs(
    EQUIPMENT_UPLOAD_FOLDER,
    exist_ok=True
)

ALLOWED_BUSINESS_DOCUMENTS = {
    "pdf",
    "jpg",
    "jpeg",
    "png"
}

# =====================================================
# UPLOAD VALIDATION
# =====================================================

MAX_BUSINESS_DOCUMENT_SIZE = 10 * 1024 * 1024   # 10 MB
MAX_EQUIPMENT_IMAGE_SIZE = 5 * 1024 * 1024      # 5 MB

ALLOWED_EQUIPMENT_IMAGES = {
    "jpg",
    "jpeg",
    "png",
    "webp"
}


# =========================================================
# PACKAGE UPLOADS
# =========================================================

PACKAGE_UPLOAD_FOLDER = os.path.join(
    UPLOAD_FOLDER,
    "packages"
)

os.makedirs(
    PACKAGE_UPLOAD_FOLDER,
    exist_ok=True
)

ALLOWED_PACKAGE_IMAGES = {
    "jpg",
    "jpeg",
    "png",
    "webp"
}

MAX_PACKAGE_IMAGE_SIZE = 5 * 1024 * 1024


def get_file_extension(filename):
    if not filename or "." not in filename:
        return ""

    return filename.rsplit(".", 1)[1].lower()


def valid_file_signature(file, extension):
    """
    Verify the actual file contents instead of trusting
    only the filename extension.
    """

    file.stream.seek(0)
    header = file.stream.read(16)
    file.stream.seek(0)

    if extension == "pdf":
        return header.startswith(b"%PDF-")

    if extension in {"jpg", "jpeg"}:
        return header.startswith(b"\xff\xd8\xff")

    if extension == "png":
        return header.startswith(
            b"\x89PNG\r\n\x1a\n"
        )

    if extension == "webp":
        return (
            header[:4] == b"RIFF"
            and header[8:12] == b"WEBP"
        )

    return False


def generate_unique_filename(original_filename):
    extension = get_file_extension(
        secure_filename(original_filename)
    )

    return f"{uuid.uuid4().hex}.{extension}"



@app.route("/business-register", methods=["GET", "POST"])
def business_register():

    if request.method == "GET":

        return render_template(
            "business_register.html"
        )


    # =========================
    # GET FORM DATA
    # =========================

    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()

    password = request.form.get("password", "")
    confirm_password = request.form.get("confirmPassword", "")

    business_name = request.form.get(
        "business_name", ""
    ).strip()

    registration_number = request.form.get(
        "registration_number", ""
    ).strip()

    address = request.form.get(
        "address", ""
    ).strip()

    city = request.form.get(
        "city", ""
    ).strip()

    description = request.form.get(
        "description", ""
    ).strip()

    document_type = request.form.get(
        "document_type", ""
    ).strip()

    registration_number = (
        request.form.get(
            "registration_number",
            ""
        )
        .strip()
        .upper()
    )
    
    document = request.files.get(
        "verification_document"
    )
    terms = request.form.get("terms")


    # =========================
    # BASIC VALIDATION
    # =========================

    if not all([
        full_name,
        email,
        phone,
        password,
        confirm_password,
        business_name,
        registration_number,
        address,
        city,
        document_type,
        terms
    ]):

        return render_template(
            "business_register.html",
            registration_error=
                "Please fill in all required fields."
        )


    if password != confirm_password:

        return render_template(
            "business_register.html",
            registration_error=
                "Passwords do not match."
        )


    if not document:

        return render_template(
            "business_register.html",
            registration_error=
                "Please upload a verification document."
        )

    
    # =========================
    # REGISTRATION NUMBER VALIDATION
    # =========================

    if document_type == "GST Certificate":

        gstin_pattern = (
            r"^[0-9]{2}[A-Z]{5}[0-9]{4}"
            r"[A-Z][1-9A-Z]Z[0-9A-Z]$"
        )

        if not re.fullmatch(
            gstin_pattern,
            registration_number
        ):

            return render_template(
                "business_register.html",
                registration_error=(
                    "Invalid GSTIN. Please enter a valid "
                    "15-character GSTIN."
                )
            )


    elif document_type == "Udyam Registration":

        udyam_pattern = (
            r"^UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}$"
        )

        if not re.fullmatch(
            udyam_pattern,
            registration_number
        ):

            return render_template(
                "business_register.html",
                registration_error=(
                    "Invalid Udyam Registration Number. "
                    "Use the format UDYAM-XX-00-0000000."
                )
            )
    # =========================
    # FILE VALIDATION
    # =========================

    filename = secure_filename(
        document.filename
    )

    if not filename:

        cursor = mysql.connection.cursor()
        cursor.close()

        return render_template(
            "business_register.html",
            registration_error="Invalid verification document."
        )

    extension = get_file_extension(filename)

    if extension not in ALLOWED_BUSINESS_DOCUMENTS:

        return render_template(
            "business_register.html",
            registration_error=(
                "Only PDF, JPG and PNG documents are allowed."
            )
        )

    # Check file size
    document.stream.seek(0, os.SEEK_END)
    document_size = document.stream.tell()
    document.stream.seek(0)

    if document_size > MAX_BUSINESS_DOCUMENT_SIZE:

        return render_template(
            "business_register.html",
            registration_error=(
                "Verification document must be 10 MB or smaller."
            )
        )

    # Check actual file contents
    if not valid_file_signature(document, extension):

        return render_template(
            "business_register.html",
            registration_error=(
                "The uploaded document does not match "
                "its file type."
            )
    )

    # =========================
    # DATABASE
    # =========================

    cursor = mysql.connection.cursor()


    try:

        # Check existing email

        cursor.execute(
            """
            SELECT id
            FROM users
            WHERE email = %s
            """,
            (email,)
        )

        existing_email = cursor.fetchone()


        if existing_email:

            cursor.close()

            return render_template(
                "business_register.html",
                registration_error=
                    "An account with this email already exists."
            )


        # Check existing phone

        cursor.execute(
            """
            SELECT id
            FROM users
            WHERE phone = %s
            """,
            (phone,)
        )

        existing_phone = cursor.fetchone()


        if existing_phone:

            cursor.close()

            return render_template(
                "business_register.html",
                registration_error=
                    "An account with this phone number already exists."
            )


        # Check registration number

        cursor.execute(
            """
            SELECT id
            FROM businesses
            WHERE registration_number = %s
            """,
            (registration_number,)
        )

        existing_registration = cursor.fetchone()


        if existing_registration:

            cursor.close()

            return render_template(
                "business_register.html",
                registration_error=
                    "This business registration number is already registered."
            )


        # =========================
        # CREATE USER
        # =========================

        hashed_password = generate_password_hash(
            password
        )


        cursor.execute(
            """
            INSERT INTO users
            (
                full_name,
                email,
                phone,
                password,
                user_type
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                'Business'
            )
            """,
            (
                full_name,
                email,
                phone,
                hashed_password
            )
        )


        user_id = cursor.lastrowid


        # =========================
        # CREATE BUSINESS
        # =========================

        cursor.execute(
            """
            INSERT INTO businesses
            (
                user_id,
                business_name,
                business_email,
                business_phone,
                registration_number,
                address,
                city,
                description,
                approval_status
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                'Pending'
            )
            """,
            (
                user_id,
                business_name,
                email,
                phone,
                registration_number,
                address,
                city,
                description
            )
        )


        business_id = cursor.lastrowid


        # =========================
        # SAVE DOCUMENT
        # =========================

        unique_filename = (
            f"business_{business_id}_"
            f"{uuid.uuid4().hex}.{extension}"
        )


        document_path = os.path.join(
            BUSINESS_DOCUMENT_FOLDER,
            unique_filename
        )


        document.save(document_path)


        # Store relative path in DB

        relative_path = (
            f"uploads/business_documents/"
            f"{unique_filename}"
        )


        cursor.execute(
            """
            INSERT INTO business_documents
            (
                business_id,
                document_type,
                document_path
            )
            VALUES
            (
                %s,
                %s,
                %s
            )
            """,
            (
                business_id,
                document_type,
                relative_path
            )
        )


        # =========================
        # COMMIT
        # =========================

        mysql.connection.commit()

        cursor.close()


        # =====================================================
        # EMAIL ADMINS ABOUT NEW REGISTRATION
        # =====================================================

        admin_cursor = mysql.connection.cursor()

        try:

            admin_cursor.execute("""
                SELECT email
                FROM users
                WHERE user_type = 'Admin'
                AND email IS NOT NULL
                AND email != ''
            """)

            admin_emails = [
                row[0]
                for row in admin_cursor.fetchall()
            ]

        finally:

            admin_cursor.close()


        for admin_email in admin_emails:

            send_email(
                admin_email,
                "New Business Registration - RentEZ",
                f"""A new business has registered on RentEZ.

        Business Name:
        {business_name}

        Owner:
        {full_name}

        Email:
        {email}

        Phone:
        {phone}

        Registration Number:
        {registration_number}

        City:
        {city}

        Status:
        Pending

        Please log in to the RentEZ Admin Panel to review
        the application and verification documents.
        """
            )


        return render_template(
            "business_register.html",
            registration_success=(
                "Your application has been submitted "
                "successfully. Our admin team will review "
                "your business details and documents. "
                "You will receive an email once your "
                "verification status has been decided."
            )
        )


    except Exception as e:

        mysql.connection.rollback()

        cursor.close()

        print(
            "Business registration error:",
            e
        )

        return render_template(
            "business_register.html",
            registration_error=(
                "Something went wrong while submitting "
                "your application. Please try again."
            )
        )
        

# =========================================================
# WISHLIST
# =========================================================

@app.route("/wishlist")
def wishlist():

    if not customer_logged_in():
        return redirect(url_for("login"))

    user_id = session["user_id"]

    cursor = mysql.connection.cursor()

    try:

        cursor.execute("""
            SELECT
                e.id,
                e.name,
                e.category,
                e.description,
                e.price_per_day,
                e.image,
                e.available
            FROM wishlist w
            JOIN equipment e
                ON w.equipment_id = e.id
            WHERE w.user_id = %s
              AND e.is_active = TRUE
            ORDER BY w.created_at DESC
        """, (
            user_id,
        ))

        wishlist_items = cursor.fetchall()

        return render_template(
            "wishlist.html",
            wishlist_items=wishlist_items,
            user_name=session["user_name"]
        )

    finally:
        cursor.close()


@app.route(
    "/wishlist/toggle/<int:equipment_id>",
    methods=["POST"]
)
def toggle_wishlist(equipment_id):

    if not customer_logged_in():

        return jsonify({
            "success": False,
            "message": "Please login as a customer."
        }), 401

    user_id = session["user_id"]

    cursor = mysql.connection.cursor()

    try:

        # Make sure equipment exists and is active
        cursor.execute("""
            SELECT id
            FROM equipment
            WHERE id = %s
              AND is_active = TRUE
        """, (
            equipment_id,
        ))

        equipment = cursor.fetchone()

        if not equipment:

            return jsonify({
                "success": False,
                "message": "Equipment not found."
            }), 404


        # Already in wishlist?
        cursor.execute("""
            SELECT id
            FROM wishlist
            WHERE user_id = %s
              AND equipment_id = %s
            LIMIT 1
        """, (
            user_id,
            equipment_id
        ))

        existing = cursor.fetchone()


        if existing:

            cursor.execute("""
                DELETE FROM wishlist
                WHERE user_id = %s
                  AND equipment_id = %s
            """, (
                user_id,
                equipment_id
            ))

            mysql.connection.commit()

            return jsonify({
                "success": True,
                "wishlisted": False,
                "message": "Removed from wishlist."
            })


        cursor.execute("""
            INSERT INTO wishlist
            (
                user_id,
                equipment_id
            )
            VALUES (%s, %s)
        """, (
            user_id,
            equipment_id
        ))

        mysql.connection.commit()

        return jsonify({
            "success": True,
            "wishlisted": True,
            "message": "Added to wishlist."
        })

    except Exception as e:

        mysql.connection.rollback()

        print(
            "Wishlist update failed:",
            e
        )

        return jsonify({
            "success": False,
            "message": "Unable to update wishlist."
        }), 500

    finally:
        cursor.close()


@app.route("/business/<int:business_id>")
def business_store(business_id):

    if not customer_logged_in():
        return redirect(url_for("login"))

    cursor = mysql.connection.cursor()

    try:

        cursor.execute("""
            SELECT
                id,
                business_name,
                city,
                address,
                description
            FROM businesses
            WHERE id = %s
              AND approval_status = 'Approved'
        """, (
            business_id,
        ))

        business = cursor.fetchone()

        if not business:
            return "Business not found.", 404


        cursor.execute("""
            SELECT
                id,
                name,
                category,
                description,
                price_per_day,
                image,
                available
            FROM equipment
            WHERE business_id = %s
              AND is_active = TRUE
            ORDER BY created_at DESC
        """, (
            business_id,
        ))

        equipment_list = cursor.fetchall()


        return render_template(
            "business_store.html",
            business=business,
            equipment_list=equipment_list,
            user_name=session["user_name"]
        )

    finally:

        cursor.close()

     
@app.route("/equipment")
def equipment():

    if not customer_logged_in():
        return redirect(url_for("login"))

    search_query = request.args.get(
        "search",
        ""
    ).strip()

    selected_category = request.args.get(
        "category",
        ""
    ).strip()

    cursor = mysql.connection.cursor()

    try:

        query = """
            SELECT
                e.id,
                e.name,
                e.category,
                e.description,
                e.price_per_day,
                e.image,
                e.available
            FROM equipment e
            JOIN businesses b
                ON e.business_id = b.id
            WHERE e.is_active = TRUE
              AND b.approval_status = 'Approved'
        """

        params = []


        if search_query:

            query += """
                AND (
                    e.name LIKE %s
                    OR e.category LIKE %s
                    OR e.description LIKE %s
                    OR b.business_name LIKE %s
                )
            """

            search_pattern = (
                f"%{search_query}%"
            )

            params.extend([
                search_pattern,
                search_pattern,
                search_pattern,
                search_pattern
            ])


        if selected_category:

            query += """
                AND e.category = %s
            """

            params.append(
                selected_category
            )


        query += """
            ORDER BY e.created_at DESC
        """


        cursor.execute(
            query,
            tuple(params)
        )

        equipment_list = cursor.fetchall()


        cursor.execute("""
            SELECT equipment_id
            FROM wishlist
            WHERE user_id = %s
        """, (
            session["user_id"],
        ))

        wishlist_ids = {
            row[0]
            for row in cursor.fetchall()
        }


        return render_template(
            "equipment.html",
            equipment_list=equipment_list,
            wishlist_ids=wishlist_ids,
            user_name=session["user_name"],
            search_query=search_query,
            selected_category=selected_category
        )

    finally:

        cursor.close()


@app.route("/equipment/<int:equipment_id>")
def equipment_details(equipment_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    cursor = mysql.connection.cursor()

    try:

        cursor.execute("""
            SELECT *
            FROM equipment
            WHERE id = %s
              AND is_active = TRUE
        """, (
            equipment_id,
        ))

        item = cursor.fetchone()

        if not item:
            return "Equipment not found", 404


        cursor.execute("""
            SELECT id
            FROM wishlist
            WHERE user_id = %s
              AND equipment_id = %s
            LIMIT 1
        """, (
            session["user_id"],
            equipment_id
        ))

        is_wishlisted = (
            cursor.fetchone() is not None
        )

        cursor.execute("""
            SELECT
                b.id,
                b.business_name,
                b.city
            FROM businesses b
            WHERE b.id = %s
            AND b.approval_status = 'Approved'
            LIMIT 1
        """, (
            item[1],
        ))

        equipment_business = cursor.fetchone()
        # ================================================
        # YOU MIGHT ALSO LIKE
        # ================================================

        cursor.execute("""
            SELECT
                id,
                name,
                category,
                description,
                price_per_day,
                image,
                available
            FROM equipment
            WHERE category = %s
              AND id != %s
              AND is_active = TRUE
            ORDER BY created_at DESC
            LIMIT 4
        """, (
            item[3],
            equipment_id
        ))

        recommended_equipment = cursor.fetchall()


        return render_template(
            "equipment_details.html",
            item=item,
            is_wishlisted=is_wishlisted,
            recommended_equipment=recommended_equipment,
            user_name=session["user_name"],
            business=equipment_business,
        )

    finally:

        cursor.close()
        
        
    
@app.route(
    "/check-availability/<int:equipment_id>"
)
def check_availability(equipment_id):

    if not customer_logged_in():

        return jsonify({
            "success": False,
            "message": "Please login as a customer."
        }), 401


    start_date = request.args.get(
        "start_date",
        ""
    ).strip()

    end_date = request.args.get(
        "end_date",
        ""
    ).strip()


    if not start_date or not end_date:

        return jsonify({
            "success": False,
            "message": "Please select both dates."
        }), 400


    try:

        start = datetime.strptime(
            start_date,
            "%Y-%m-%d"
        ).date()

        end = datetime.strptime(
            end_date,
            "%Y-%m-%d"
        ).date()

    except ValueError:

        return jsonify({
            "success": False,
            "message": "Invalid date."
        }), 400


    total_days = (
        end - start
    ).days


    if total_days <= 0:

        return jsonify({
            "success": False,
            "message": (
                "End date must be after "
                "the start date."
            )
        }), 400


    if total_days > 30:

        return jsonify({
            "success": False,
            "message": (
                "Rental period cannot "
                "exceed 30 days."
            )
        }), 400


    cursor = mysql.connection.cursor()


    try:

        cursor.execute("""
            SELECT
                total_quantity
            FROM equipment
            WHERE id = %s
              AND is_active = TRUE
        """, (
            equipment_id,
        ))


        equipment = cursor.fetchone()


        if not equipment:

            return jsonify({
                "success": False,
                "message": "Equipment not found."
            }), 404


        max_quantity = (
            get_max_cart_quantity(
                cursor,
                "Equipment",
                equipment_id,
                start,
                end
            )
        )


        return jsonify({

            "success": True,

            "available_quantity":
                max_quantity,

            "max_quantity":
                max_quantity,

            "total_quantity":
                int(equipment[0])

        })


    finally:

        cursor.close()
    

# =========================================================
# CUSTOMER CART
# =========================================================

@app.route("/cart")
def cart():

    if not customer_logged_in():
        return redirect(url_for("login"))


    cart = get_cart()

    cursor = mysql.connection.cursor()


    try:

        # =================================================
        # BUILD CART ITEMS
        # =================================================

        cart_items = []


        for cart_item in cart["items"]:

            item_type = cart_item["item_type"]

            item_id = int(
                cart_item["item_id"]
            )

            quantity = int(
                cart_item["quantity"]
            )


            # ---------------------------------------------
            # EQUIPMENT
            # ---------------------------------------------

            if item_type == "Equipment":

                cursor.execute("""
                    SELECT
                        e.id,
                        e.name,
                        e.category,
                        e.description,
                        e.price_per_day,
                        e.image,
                        e.available,
                        e.business_id,
                        b.business_name,
                        b.city
                    FROM equipment e

                    JOIN businesses b
                        ON e.business_id = b.id

                    WHERE e.id = %s
                      AND e.is_active = TRUE
                      AND b.approval_status = 'Approved'
                """, (
                    item_id,
                ))


                row = cursor.fetchone()


                if not row:
                    continue


                cart_items.append({

                    "key":
                        cart_item_key(
                            "Equipment",
                            item_id
                        ),

                    "item_type":
                        "Equipment",

                    "item_id":
                        item_id,

                    "name":
                        row[1],

                    "category":
                        row[2],

                    "description":
                        row[3],

                    "unit_price":
                        float(row[4]),

                    "image":
                        row[5],

                    "available":
                        bool(row[6]),

                    "business_id":
                        row[7],

                    "business_name":
                        row[8],

                    "city":
                        row[9],

                    "quantity":
                        quantity

                })


            # ---------------------------------------------
            # PACKAGE
            # ---------------------------------------------

            elif item_type == "Package":

                cursor.execute("""
                    SELECT
                        p.id,
                        p.name,
                        p.description,
                        p.price_per_day,
                        p.image,
                        p.business_id,
                        b.business_name,
                        b.city
                    FROM packages p

                    JOIN businesses b
                        ON p.business_id = b.id

                    WHERE p.id = %s
                      AND p.is_active = TRUE
                      AND b.approval_status = 'Approved'
                """, (
                    item_id,
                ))


                row = cursor.fetchone()


                if not row:
                    continue


                cart_items.append({

                    "key":
                        cart_item_key(
                            "Package",
                            item_id
                        ),

                    "item_type":
                        "Package",

                    "item_id":
                        item_id,

                    "name":
                        row[1],

                    "description":
                        row[2],

                    "unit_price":
                        float(row[3]),

                    "image":
                        row[4],

                    "available":
                        True,

                    "business_id":
                        row[5],

                    "business_name":
                        row[6],

                    "city":
                        row[7],

                    "quantity":
                        quantity

                })


        # =================================================
        # CALCULATE SUBTOTAL + RENTAL DAYS
        # =================================================

        subtotal = 0

        total_days = 0

        start = None

        end = None


        if (
            cart["start_date"]
            and cart["end_date"]
        ):

            try:

                start = datetime.strptime(
                    cart["start_date"],
                    "%Y-%m-%d"
                ).date()


                end = datetime.strptime(
                    cart["end_date"],
                    "%Y-%m-%d"
                ).date()


                total_days = (
                    end - start
                ).days


                if total_days > 0:

                    subtotal = sum(

                        item["unit_price"]

                        * item["quantity"]

                        * total_days

                        for item in cart_items

                    )

                else:

                    total_days = 0


            except ValueError:

                total_days = 0

                start = None

                end = None


        # =================================================
        # CALCULATE MAX QUANTITY FOR EACH CART ITEM
        # =================================================

        if (
            start
            and end
            and total_days > 0
        ):

            for item in cart_items:

                item["max_quantity"] = min(

                    get_max_cart_quantity(

                        cursor,

                        item["item_type"],

                        item["item_id"],

                        start,

                        end

                    ),

                    100

                )

        else:

            for item in cart_items:

                item["max_quantity"] = 100


        # =================================================
        # RECOMMENDATIONS
        # ONLY ONE CLEAN RECOMMENDATION ROW
        # =================================================

        recommended_items = []


        cart_equipment_ids = [

            int(item["item_id"])

            for item in cart_items

            if item["item_type"] == "Equipment"

        ]


        if cart_equipment_ids:

            placeholders = ",".join(
                ["%s"] * len(
                    cart_equipment_ids
                )
            )


            recommendation_sql = f"""
                SELECT
                    e.id,
                    e.name,
                    e.category,
                    e.price_per_day,
                    e.image,
                    b.business_name

                FROM equipment e

                JOIN businesses b
                    ON e.business_id = b.id

                WHERE e.is_active = TRUE
                  AND e.available = TRUE
                  AND e.available_quantity > 0
                  AND b.approval_status = 'Approved'
                  AND e.id NOT IN ({placeholders})

                ORDER BY RAND()

                LIMIT 4
            """


            cursor.execute(

                recommendation_sql,

                tuple(
                    cart_equipment_ids
                )

            )


        else:

            cursor.execute("""
                SELECT
                    e.id,
                    e.name,
                    e.category,
                    e.price_per_day,
                    e.image,
                    b.business_name

                FROM equipment e

                JOIN businesses b
                    ON e.business_id = b.id

                WHERE e.is_active = TRUE
                  AND e.available = TRUE
                  AND e.available_quantity > 0
                  AND b.approval_status = 'Approved'

                ORDER BY RAND()

                LIMIT 4
            """)


        for row in cursor.fetchall():

            recommended_items.append({

                "id":
                    row[0],

                "name":
                    row[1],

                "category":
                    row[2],

                "price":
                    float(row[3]),

                "image":
                    row[4],

                "business_name":
                    row[5]

            })


        # =================================================
        # RENDER CART
        # =================================================

        return render_template(

            "cart.html",

            cart_items=cart_items,

            start_date=
                cart["start_date"],

            end_date=
                cart["end_date"],

            total_days=
                total_days,

            subtotal=
                subtotal,

            user_name=
                session["user_name"],

            cart_count=
                get_cart_count(),

            recommended_items=
                recommended_items

        )


    finally:

        cursor.close()


@app.route(
    "/cart/add-equipment/<int:equipment_id>",
    methods=["POST"]
)
def add_equipment_to_cart(equipment_id):

    if not customer_logged_in():
        return redirect(url_for("login"))

    start_date = request.form.get(
        "start_date",
        ""
    ).strip()

    end_date = request.form.get(
        "end_date",
        ""
    ).strip()

    quantity = request.form.get(
        "quantity",
        "1"
    ).strip()

    try:

        quantity = int(quantity)

    except ValueError:

        return "Invalid quantity.", 400

    if quantity < 1:
        return "Invalid quantity.", 400

    try:

        start = datetime.strptime(
            start_date,
            "%Y-%m-%d"
        ).date()

        end = datetime.strptime(
            end_date,
            "%Y-%m-%d"
        ).date()

    except ValueError:

        return "Invalid rental dates.", 400

    total_days = (
        end - start
    ).days

    if total_days <= 0:
        return "End date must be after start date.", 400

    if total_days > 30:
        return "Rental period cannot exceed 30 days.", 400

    cursor = mysql.connection.cursor()

    try:

        cursor.execute("""
            SELECT
                id,
                name,
                price_per_day,
                total_quantity,
                business_id
            FROM equipment
            WHERE id = %s
              AND is_active = TRUE
        """, (
            equipment_id,
        ))

        equipment = cursor.fetchone()

        if not equipment:
            return "Equipment not found.", 404

        total_quantity = int(
            equipment[3]
        )

        available = (
            get_equipment_available_quantity(
                cursor,
                equipment_id,
                start,
                end
            )
        )

        cart = get_cart()

        # -------------------------------------------------
        # CART DATE CONSISTENCY
        # -------------------------------------------------

        if cart["items"]:

            if (
                cart["start_date"] != start_date
                or cart["end_date"] != end_date
            ):

                flash(
                    "Your cart already uses different rental dates. "
                    "Please use the same dates or clear your cart first.",
                    "cart_error"
                )

                return redirect(
                    url_for(
                        "rent_equipment",
                        equipment_id=equipment_id
                    )
                )

        else:

            cart["start_date"] = start_date
            cart["end_date"] = end_date

        key = cart_item_key(
            "Equipment",
            equipment_id
        )

        existing = next(
            (
                item
                for item in cart["items"]
                if item["key"] == key
            ),
            None
        )

        if existing:

            new_quantity = (
                existing["quantity"]
                + quantity
            )

        else:

            new_quantity = quantity

        if new_quantity > available:

            return (
                f"Only {available} unit(s) "
                "are available for those dates.",
                400
            )

        if existing:

            existing["quantity"] = new_quantity

        else:

            cart["items"].append({
                "key": key,
                "item_type": "Equipment",
                "item_id": equipment_id,
                "quantity": quantity
            })

        save_cart(cart)

        return redirect(
            url_for("cart")
        )

    finally:

        cursor.close()


@app.route(
    "/cart/add-package/<int:package_id>",
    methods=["POST"]
)
def add_package_to_cart(package_id):

    if not customer_logged_in():
        return redirect(url_for("login"))

    start_date = request.form.get(
        "start_date",
        ""
    ).strip()

    end_date = request.form.get(
        "end_date",
        ""
    ).strip()

    quantity = request.form.get(
        "quantity",
        "1"
    ).strip()

    try:
        quantity = int(quantity)
    except ValueError:
        return "Invalid quantity.", 400

    if quantity < 1:
        return "Invalid quantity.", 400

    try:
        start = datetime.strptime(
            start_date,
            "%Y-%m-%d"
        ).date()

        end = datetime.strptime(
            end_date,
            "%Y-%m-%d"
        ).date()

    except ValueError:
        return "Invalid rental dates.", 400

    total_days = (end - start).days

    if total_days <= 0:
        return "End date must be after start date.", 400

    if total_days > 30:
        return "Rental period cannot exceed 30 days.", 400

    cursor = mysql.connection.cursor()

    try:

        package_data = get_package_availability(
            cursor,
            package_id,
            start,
            end
        )

        if not package_data:
            return "Package not found.", 404

        available_packages = int(
            package_data["available_packages"]
        )


        # =================================================
        # ACCOUNT FOR ITEMS ALREADY IN THE CART
        # =================================================

        cart = get_cart()


        cart_requirements = (
            get_cart_physical_requirements(
                cursor
            )
        )


        available_to_add = (
            available_packages
        )


        for component in package_data["items"]:

            equipment_id = int(
                component[0]
            )

            required_quantity = int(
                component[1]
            )

            cart_reserved = int(
                cart_requirements.get(
                    equipment_id,
                    0
                )
            )


            if cart_reserved <= 0:
                continue


            cursor.execute("""
                SELECT
                    total_quantity
                FROM equipment
                WHERE id = %s
                AND is_active = TRUE
            """, (
                equipment_id,
            ))

            equipment_row = cursor.fetchone()

            if not equipment_row:

                available_to_add = 0

                break


            total_quantity = int(
                equipment_row[0] or 0
            )


            # Direct paid bookings
            cursor.execute("""
                SELECT
                    COALESCE(
                        SUM(quantity),
                        0
                    )
                FROM bookings
                WHERE equipment_id = %s
                AND payment_status = 'Paid'
                AND booking_status IN (
                        'Confirmed',
                        'Out for Delivery',
                        'Delivered'
                )
                AND start_date < %s
                AND end_date > %s
            """, (
                equipment_id,
                end,
                start
            ))

            direct_reserved = int(
                cursor.fetchone()[0] or 0
            )


            # Package bookings
            cursor.execute("""
                SELECT
                    COALESCE(
                        SUM(bi.quantity),
                        0
                    )
                FROM booking_items bi
                JOIN bookings b
                    ON b.id = bi.booking_id
                WHERE bi.equipment_id = %s
                AND b.package_id IS NOT NULL
                AND b.payment_status = 'Paid'
                AND b.booking_status IN (
                        'Confirmed',
                        'Out for Delivery',
                        'Delivered'
                )
                AND b.start_date < %s
                AND b.end_date > %s
            """, (
                equipment_id,
                end,
                start
            ))

            package_reserved = int(
                cursor.fetchone()[0] or 0
            )


            available_units = max(
                total_quantity
                - direct_reserved
                - package_reserved
                - cart_reserved,
                0
            )


            component_capacity = (
                available_units
                // required_quantity
            )


            available_to_add = min(
                available_to_add,
                component_capacity
            )


        if quantity > available_to_add:

            return (
                f"Only {available_to_add} "
                "additional package(s) are available "
                "for those dates.",
                400
            )

        cart = get_cart()

        # Same dates for every cart item
        if cart["items"]:

            if (
                cart["start_date"] != start_date
                or cart["end_date"] != end_date
            ):

                flash(
                    "Your cart already uses different rental dates. "
                    "Please use the same dates or clear your cart first.",
                    "cart_error"
                )

                return redirect(
                    url_for(
                        "rent_package",
                        package_id=package_id
                    )
                )

        else:

            cart["start_date"] = start_date
            cart["end_date"] = end_date

        key = cart_item_key(
            "Package",
            package_id
        )

        existing = next(
            (
                item
                for item in cart["items"]
                if item["key"] == key
            ),
            None
        )

        if existing:

            new_quantity = (
                existing["quantity"] + quantity
            )

            existing["quantity"] = new_quantity

        else:

            cart["items"].append({
                "key": key,
                "item_type": "Package",
                "item_id": package_id,
                "quantity": quantity
            })

        save_cart(cart)

        return redirect(
            url_for("cart")
        )

    finally:
        cursor.close()


@app.route(
    "/cart/change-quantity",
    methods=["POST"]
)
def change_cart_quantity():

    if not customer_logged_in():

        return jsonify({
            "success": False,
            "message": "Please login as a customer."
        }), 401


    data = request.get_json(
        silent=True
    ) or {}


    item_type = str(
        data.get(
            "item_type",
            ""
        )
    ).strip()


    try:

        item_id = int(
            data.get("item_id")
        )

    except (
        TypeError,
        ValueError
    ):

        return jsonify({
            "success": False,
            "message": "Invalid item."
        }), 400


    action = str(
        data.get(
            "action",
            ""
        )
    ).strip().lower()


    if item_type not in {
        "Equipment",
        "Package"
    }:

        return jsonify({
            "success": False,
            "message": "Invalid item type."
        }), 400


    if action not in {
        "add",
        "increase",
        "decrease"
    }:

        return jsonify({
            "success": False,
            "message": "Invalid quantity action."
        }), 400


    cart = get_cart()


    key = cart_item_key(
        item_type,
        item_id
    )


    target = next(
        (
            item
            for item in cart["items"]
            if item.get("key") == key
        ),
        None
    )


    current_quantity = int(
        target.get(
            "quantity",
            0
        )
        if target
        else 0
    )


    # =================================================
    # DECREASE
    # =================================================

    if action == "decrease":

        if current_quantity <= 0:

            return jsonify({
                "success": True,
                "quantity": 0,
                "cart_count":
                    get_cart_count(),
                "cart_empty":
                    not cart["items"]
            })


        new_quantity = (
            current_quantity - 1
        )


        # ---------------------------------------------
        # REMOVE COMPLETELY
        # ---------------------------------------------

        if new_quantity == 0:

            cart["items"] = [

                item
                for item in cart["items"]

                if item.get("key") != key

            ]


            if not cart["items"]:

                cart["start_date"] = None

                cart["end_date"] = None


            save_cart(cart)


            return jsonify({

                "success": True,

                "quantity": 0,

                "cart_count":
                    get_cart_count(),

                "cart_empty":
                    not cart["items"]

            })


        target["quantity"] = (
            new_quantity
        )


        save_cart(cart)


        return jsonify({

            "success": True,

            "quantity":
                new_quantity,

            "cart_count":
                get_cart_count(),

            "cart_empty":
                False

        })


    # =================================================
    # ADD / INCREASE
    # =================================================

    start_date = str(
        data.get(
            "start_date",
            ""
        )
    ).strip()

    end_date = str(
        data.get(
            "end_date",
            ""
        )
    ).strip()


    # Existing cart dates always win.

    if cart["items"]:

        start_date = (
            cart.get("start_date")
            or ""
        )

        end_date = (
            cart.get("end_date")
            or ""
        )


    if not start_date or not end_date:

        return jsonify({
            "success": False,
            "message": (
                "Please select both "
                "rental dates first."
            )
        }), 400


    try:

        start = datetime.strptime(
            start_date,
            "%Y-%m-%d"
        ).date()

        end = datetime.strptime(
            end_date,
            "%Y-%m-%d"
        ).date()

    except ValueError:

        return jsonify({
            "success": False,
            "message": "Invalid rental dates."
        }), 400


    total_days = (
        end - start
    ).days


    if total_days <= 0:

        return jsonify({
            "success": False,
            "message": (
                "End date must be after "
                "the start date."
            )
        }), 400


    if total_days > 30:

        return jsonify({
            "success": False,
            "message": (
                "Rental period cannot "
                "exceed 30 days."
            )
        }), 400


    # First item establishes the cart dates.

    if not cart["items"]:

        cart["start_date"] = start_date
        cart["end_date"] = end_date


    requested_quantity = (
        current_quantity + 1
    )


    if requested_quantity > 100:

        return jsonify({

            "success": False,

            "message":
                "Maximum quantity is 100.",

            "max_quantity":
                100,

            "quantity":
                current_quantity

        }), 400


    cursor = mysql.connection.cursor()


    try:

        # ---------------------------------------------
        # VERIFY ITEM
        # ---------------------------------------------

        if item_type == "Equipment":

            cursor.execute("""
                SELECT
                    id,
                    name,
                    price_per_day
                FROM equipment
                WHERE id = %s
                  AND is_active = TRUE
            """, (
                item_id,
            ))


            item_row = (
                cursor.fetchone()
            )


            if not item_row:

                return jsonify({
                    "success": False,
                    "message": (
                        "Equipment is "
                        "no longer available."
                    )
                }), 404


        else:

            package_data = (
                get_package_availability(
                    cursor,
                    item_id,
                    start,
                    end
                )
            )


            if not package_data:

                return jsonify({
                    "success": False,
                    "message": (
                        "Package is "
                        "no longer available."
                    )
                }), 404


            item_row = (

                package_data["package"][0],

                package_data["package"][2],

                package_data["package"][5]

            )


        # ---------------------------------------------
        # MAX ALLOWED TOTAL QUANTITY
        # ---------------------------------------------

        max_quantity = (
            get_max_cart_quantity(
                cursor,
                item_type,
                item_id,
                start,
                end
            )
        )


        if requested_quantity > max_quantity:

            label = (

                "unit(s)"
                if item_type == "Equipment"
                else "package(s)"

            )


            return jsonify({

                "success": False,

                "message": (
                    f"Only {max_quantity} "
                    f"{label} are available "
                    "for those dates."
                ),

                "max_quantity":
                    max_quantity,

                "quantity":
                    current_quantity

            }), 400


        # ---------------------------------------------
        # SAVE QUANTITY
        # ---------------------------------------------

        if target:

            target["quantity"] = (
                requested_quantity
            )

        else:

            cart["items"].append({

                "key": key,

                "item_type":
                    item_type,

                "item_id":
                    item_id,

                "quantity":
                    requested_quantity

            })


        save_cart(cart)


        line_total = (

            float(item_row[2])

            * requested_quantity

            * total_days

        )


        return jsonify({

            "success": True,

            "quantity":
                requested_quantity,

            "max_quantity":
                max_quantity,

            "cart_count":
                get_cart_count(),

            "cart_empty":
                False,

            "unit_price":
                float(item_row[2]),

            "total_days":
                total_days,

            "line_total":
                line_total

        })


    finally:

        cursor.close()
        

@app.route(
    "/cart/remove/<item_type>/<int:item_id>",
    methods=["POST"]
)
def remove_from_cart(item_type, item_id):

    if not customer_logged_in():
        return redirect(url_for("login"))

    cart = get_cart()

    item_key = cart_item_key(
        item_type,
        item_id
    )

    cart["items"] = [
        item
        for item in cart["items"]
        if item["key"] != item_key
    ]

    if not cart["items"]:

        cart["start_date"] = None
        cart["end_date"] = None

    save_cart(cart)

    return redirect(
        url_for("cart")
    )


@app.route(
    "/cart/update",
    methods=["POST"]
)
def update_cart():

    if not customer_logged_in():
        return redirect(url_for("login"))

    cart = get_cart()

    for item in cart["items"]:

        raw_quantity = request.form.get(
            f"quantity_{item['key']}",
            ""
        )

        try:

            quantity = int(
                raw_quantity
            )

        except ValueError:

            continue

        if quantity < 1:
            continue
 
        # Do not allow obviously invalid cart quantities.
        # Final availability is still checked server-side at checkout.

        if quantity > 100:
            quantity = 100

        item["quantity"] = quantity

    save_cart(cart)

    return redirect(
        url_for("cart")
    )


@app.route(
    "/cart/clear",
    methods=["POST"]
)
def clear_customer_cart():

    if not customer_logged_in():
        return redirect(url_for("login"))

    clear_cart()

    return redirect(
        url_for("cart")
    )

@app.route(
    "/rent/<int:equipment_id>"
)
def rent_equipment(equipment_id):

    if not customer_logged_in():

        return redirect(
            url_for("login")
        )


    cursor = mysql.connection.cursor()


    try:

        cursor.execute("""
            SELECT
                id,
                name,
                category,
                description,
                price_per_day,
                image,
                available,
                total_quantity,
                available_quantity
            FROM equipment
            WHERE id = %s
              AND is_active = TRUE
        """, (
            equipment_id,
        ))


        item = cursor.fetchone()


        if not item:

            return (
                "Equipment not found",
                404
            )


        cart = get_cart()


        key = cart_item_key(
            "Equipment",
            equipment_id
        )


        existing = next(
            (
                cart_item
                for cart_item in cart["items"]
                if cart_item.get("key") == key
            ),
            None
        )


        current_quantity = int(

            existing.get(
                "quantity",
                0
            )

            if existing

            else 0

        )


        return render_template(

            "rent.html",

            item=item,

            current_quantity=
                current_quantity,

            cart_start_date=
                cart.get(
                    "start_date"
                ),

            cart_end_date=
                cart.get(
                    "end_date"
                ),

            cart_has_items=
                bool(cart["items"]),

            user_name=
                session["user_name"]

        )


    finally:

        cursor.close()

@app.route(
    "/checkout",
    methods=["GET", "POST"]
)
def checkout():

    if not customer_logged_in():
        return redirect(url_for("login"))

    cart = get_cart()

    if not cart["items"]:
        return redirect(url_for("cart"))

    if (
        not cart["start_date"]
        or not cart["end_date"]
    ):
        return redirect(url_for("cart"))

    try:

        start_date = datetime.strptime(
            cart["start_date"],
            "%Y-%m-%d"
        ).date()

        end_date = datetime.strptime(
            cart["end_date"],
            "%Y-%m-%d"
        ).date()

    except ValueError:

        clear_cart()

        return redirect(
            url_for("cart")
        )

    total_days = (
        end_date - start_date
    ).days

    if total_days <= 0:
        return redirect(url_for("cart"))

    if total_days > 30:
        return "Rental period cannot exceed 30 days.", 400

    cursor = mysql.connection.cursor()

    try:
        
        
        
        # =================================================
        # CUSTOMER ADDRESS
        # =================================================

        cursor.execute("""
            SELECT
                full_name,
                email,
                phone,
                delivery_address,
                delivery_city,
                delivery_state,
                delivery_pincode
            FROM users
            WHERE id = %s
              AND user_type = 'Customer'
        """, (
            session["user_id"],
        ))

        customer = cursor.fetchone()

        if not customer:
            session.clear()
            return redirect(url_for("login"))

        # =================================================
        # VALIDATE CART + CALCULATE TOTALS
        # =================================================

        checkout_items = []

        subtotal = 0

        for cart_item in cart["items"]:

            item_type = cart_item["item_type"]
            item_id = int(cart_item["item_id"])
            quantity = int(cart_item["quantity"])

            if quantity < 1:
                return "Invalid cart quantity.", 400

            if item_type == "Equipment":

                cursor.execute("""
                    SELECT
                        e.id,
                        e.name,
                        e.price_per_day,
                        e.business_id,
                        e.is_active,
                        b.business_name,
                        b.approval_status
                    FROM equipment e
                    JOIN businesses b
                        ON e.business_id = b.id
                    WHERE e.id = %s
                """, (
                    item_id,
                ))

                row = cursor.fetchone()

                if not row:
                    return "An equipment item in your cart no longer exists.", 400

                if not row[4] or row[6] != "Approved":
                    return (
                        f'"{row[1]}" is no longer available.',
                        400
                    )

                available = (
                    get_equipment_available_quantity(
                        cursor,
                        item_id,
                        start_date,
                        end_date
                    )
                )

                if quantity > available:
                    return (
                        f'"{row[1]}" only has '
                        f'{available} unit(s) available '
                        'for those dates.',
                        400
                    )

                unit_price = float(row[2])

                item_total = (
                    unit_price
                    * quantity
                    * total_days
                )

                checkout_items.append({
                    "item_type": "Equipment",
                    "item_id": item_id,
                    "name": row[1],
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "business_id": row[3],
                    "business_name": row[5]
                })

            elif item_type == "Package":

                package_data = get_package_availability(
                    cursor,
                    item_id,
                    start_date,
                    end_date
                )

                if not package_data:
                    return (
                        "A package in your cart is no longer available.",
                        400
                    )

                available_packages = int(
                    package_data["available_packages"]
                )

                if quantity > available_packages:

                    return (
                        f'"{package_data["package"][2]}" '
                        f'only has {available_packages} '
                        'package(s) available.',
                        400
                    )

                package = package_data["package"]

                unit_price = float(package[5])

                item_total = (
                    unit_price
                    * quantity
                    * total_days
                )

                checkout_items.append({
                    "item_type": "Package",
                    "item_id": item_id,
                    "name": package[2],
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "business_id": package[6],
                    "business_name": package[7]
                })

            else:

                return "Invalid cart item.", 400

            subtotal += item_total

        subtotal = round(
            subtotal,
            2
        )

        # -------------------------------------------------
        # DELIVERY FEE
        # Keep it zero for now; don't invent a charge.
        # -------------------------------------------------

        delivery_fee = 0

        total_amount = round(
            subtotal + delivery_fee,
            2
        )

        return render_template(
            "checkout.html",
            customer=customer,
            checkout_items=checkout_items,
            start_date=start_date,
            end_date=end_date,
            total_days=total_days,
            subtotal=subtotal,
            delivery_fee=delivery_fee,
            total_amount=total_amount,
            cart_count=get_cart_count()
        )

    finally:

        cursor.close()


@app.route(
    "/create-order",
    methods=["POST"]
)
def create_order():

    if not customer_logged_in():
        return redirect(url_for("login"))

    cart = get_cart()

    if not cart["items"]:
        return redirect(url_for("cart"))

    delivery_address = request.form.get(
        "delivery_address",
        ""
    ).strip()

    delivery_city = request.form.get(
        "delivery_city",
        ""
    ).strip()

    delivery_state = request.form.get(
        "delivery_state",
        ""
    ).strip()

    delivery_pincode = request.form.get(
        "delivery_pincode",
        ""
    ).strip()

    if not all([
        delivery_address,
        delivery_city,
        delivery_state,
        delivery_pincode
    ]):
        return redirect(
            url_for("checkout")
        )

    if (
        not delivery_pincode.isdigit()
        or len(delivery_pincode) != 6
    ):
        return redirect(
            url_for("checkout")
        )

    try:

        start_date = datetime.strptime(
            cart["start_date"],
            "%Y-%m-%d"
        ).date()

        end_date = datetime.strptime(
            cart["end_date"],
            "%Y-%m-%d"
        ).date()

    except ValueError:

        return redirect(
            url_for("cart")
        )

    total_days = (
        end_date - start_date
    ).days

    if total_days <= 0 or total_days > 30:
        return redirect(
            url_for("cart")
        )

    cursor = mysql.connection.cursor()

    try:

        # =================================================
        # REBUILD + REVALIDATE CART
        # =================================================

        validated_items = []

        subtotal = 0

        for cart_item in cart["items"]:

            item_type = cart_item["item_type"]
            item_id = int(cart_item["item_id"])
            quantity = int(cart_item["quantity"])

            if quantity < 1:
                raise ValueError(
                    "Invalid cart quantity."
                )

            if item_type == "Equipment":

                cursor.execute("""
                    SELECT
                        e.id,
                        e.name,
                        e.price_per_day,
                        e.business_id,
                        e.total_quantity,
                        e.is_active,
                        b.business_name,
                        b.approval_status
                    FROM equipment e
                    JOIN businesses b
                        ON e.business_id = b.id
                    WHERE e.id = %s
                    FOR UPDATE
                """, (
                    item_id,
                ))

                row = cursor.fetchone()

                if not row:
                    raise ValueError(
                        "Equipment no longer exists."
                    )

                if not row[5] or row[7] != "Approved":
                    raise ValueError(
                        f"{row[1]} is no longer available."
                    )

                available = (
                    get_equipment_available_quantity(
                        cursor,
                        item_id,
                        start_date,
                        end_date
                    )
                )

                if quantity > available:
                    raise ValueError(
                        f"Only {available} unit(s) of "
                        f"{row[1]} are available."
                    )

                unit_price = float(row[2])

                subtotal += (
                    unit_price
                    * quantity
                    * total_days
                )

                validated_items.append({
                    "type": "Equipment",
                    "id": item_id,
                    "name": row[1],
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "business_id": row[3]
                })

            elif item_type == "Package":

                package_data = get_package_availability(
                    cursor,
                    item_id,
                    start_date,
                    end_date
                )

                if not package_data:
                    raise ValueError(
                        "Package is no longer available."
                    )

                if quantity > int(
                    package_data["available_packages"]
                ):
                    raise ValueError(
                        "Package is no longer available "
                        "in the requested quantity."
                    )

                package = package_data["package"]

                unit_price = float(
                    package[5]
                )

                subtotal += (
                    unit_price
                    * quantity
                    * total_days
                )

                validated_items.append({
                    "type": "Package",
                    "id": item_id,
                    "name": package[2],
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "business_id": package[6]
                })

            else:

                raise ValueError(
                    "Invalid cart item."
                )

        # =================================================
        # COMBINED PHYSICAL INVENTORY CHECK
        # =================================================

        combined_inventory_result = validate_combined_inventory(
            cursor,
            validated_items,
            start_date,
            end_date
        )

        if not combined_inventory_result["success"]:

            raise ValueError(
                combined_inventory_result["message"]
            )
        
        subtotal = round(
            subtotal,
            2
        )

        delivery_fee = 0

        total_amount = round(
            subtotal + delivery_fee,
            2
        )

        if total_amount <= 0:
            raise ValueError(
                "Invalid order total."
            )

        # =================================================
        # CREATE ORDER
        # =================================================

        cursor.execute("""
            INSERT INTO orders (
                user_id,
                start_date,
                end_date,
                total_days,
                subtotal,
                delivery_fee,
                total_amount,
                delivery_address,
                delivery_city,
                delivery_state,
                delivery_pincode,
                order_status,
                payment_status
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                'Pending',
                'Pending'
            )
        """, (
            session["user_id"],
            start_date,
            end_date,
            total_days,
            subtotal,
            delivery_fee,
            total_amount,
            delivery_address,
            delivery_city,
            delivery_state,
            delivery_pincode
        ))

        order_id = cursor.lastrowid

        # =================================================
        # CREATE BOOKINGS + ORDER ITEMS
        # =================================================

        first_booking_id = None

        for item in validated_items:

            if item["type"] == "Equipment":

                cursor.execute("""
                    INSERT INTO bookings (
                        user_id,
                        equipment_id,
                        package_id,
                        order_id,
                        quantity,
                        start_date,
                        end_date,
                        total_days,
                        daily_rate,
                        total_amount,
                        delivery_address,
                        delivery_city,
                        delivery_state,
                        delivery_pincode,
                        booking_status,
                        payment_status
                    )
                    VALUES (
                        %s,
                        %s,
                        NULL,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        'Pending',
                        'Pending'
                    )
                """, (
                    session["user_id"],
                    item["id"],
                    order_id,
                    item["quantity"],
                    start_date,
                    end_date,
                    total_days,
                    item["unit_price"],
                    item["unit_price"]
                    * item["quantity"]
                    * total_days,
                    delivery_address,
                    delivery_city,
                    delivery_state,
                    delivery_pincode
                ))

                booking_id = cursor.lastrowid

                if first_booking_id is None:
                    first_booking_id = booking_id

                # Snapshot the equipment into booking_items
                cursor.execute("""
                    INSERT INTO booking_items (
                        booking_id,
                        equipment_id,
                        quantity,
                        unit_price,
                        item_name,
                        source
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        'Equipment'
                    )
                """, (
                    booking_id,
                    item["id"],
                    item["quantity"],
                    item["unit_price"],
                    item["name"]
                ))

                cursor.execute("""
                    INSERT INTO order_items (
                        order_id,
                        equipment_id,
                        package_id,
                        item_type,
                        item_name,
                        quantity,
                        unit_price,
                        business_id
                    )
                    VALUES (
                        %s,
                        %s,
                        NULL,
                        'Equipment',
                        %s,
                        %s,
                        %s,
                        %s
                    )
                """, (
                    order_id,
                    item["id"],
                    item["name"],
                    item["quantity"],
                    item["unit_price"],
                    item["business_id"]
                ))

            else:

                cursor.execute("""
                    INSERT INTO bookings (
                        user_id,
                        equipment_id,
                        package_id,
                        order_id,
                        quantity,
                        start_date,
                        end_date,
                        total_days,
                        daily_rate,
                        total_amount,
                        delivery_address,
                        delivery_city,
                        delivery_state,
                        delivery_pincode,
                        booking_status,
                        payment_status
                    )
                    VALUES (
                        %s,
                        NULL,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        'Pending',
                        'Pending'
                    )
                """, (
                    session["user_id"],
                    item["id"],
                    order_id,
                    item["quantity"],
                    start_date,
                    end_date,
                    total_days,
                    item["unit_price"],
                    item["unit_price"]
                    * item["quantity"]
                    * total_days,
                    delivery_address,
                    delivery_city,
                    delivery_state,
                    delivery_pincode
                ))

                booking_id = cursor.lastrowid

                if first_booking_id is None:
                    first_booking_id = booking_id

                # Snapshot package components
                package_data = get_package_availability(
                    cursor,
                    item["id"],
                    start_date,
                    end_date
                )

                for component in package_data["items"]:

                    component_quantity = (
                        int(component[1])
                        * item["quantity"]
                    )

                    cursor.execute("""
                        INSERT INTO booking_items (
                            booking_id,
                            equipment_id,
                            quantity,
                            unit_price,
                            item_name,
                            source
                        )
                        VALUES (
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            'Package'
                        )
                    """, (
                        booking_id,
                        component[0],
                        component_quantity,
                        float(component[5]),
                        component[2]
                    ))

                cursor.execute("""
                    INSERT INTO order_items (
                        order_id,
                        equipment_id,
                        package_id,
                        item_type,
                        item_name,
                        quantity,
                        unit_price,
                        business_id
                    )
                    VALUES (
                        %s,
                        NULL,
                        %s,
                        'Package',
                        %s,
                        %s,
                        %s,
                        %s
                    )
                """, (
                    order_id,
                    item["id"],
                    item["name"],
                    item["quantity"],
                    item["unit_price"],
                    item["business_id"]
                ))

        # =================================================
        # STORE ORDER IN SESSION
        # =================================================

        session["pending_order_id"] = order_id

        mysql.connection.commit()

        return redirect(
            url_for(
                "order_payment",
                order_id=order_id
            )
        )

    except Exception as e:

        mysql.connection.rollback()

        print(
            "Order creation failed:",
            e
        )

        return (
            "Unable to create your order. "
            "Please review your cart and try again.",
            400
        )

    finally:
        cursor.close()


        
# =========================================================
# ORDER PAYMENT
# =========================================================

@app.route("/order-payment/<int:order_id>")
def order_payment(order_id):

    if not customer_logged_in():
        return redirect(url_for("login"))

    cursor = mysql.connection.cursor()

    try:

        # -------------------------------------------------
        # GET ORDER
        # -------------------------------------------------

        cursor.execute("""
            SELECT
                id,
                user_id,
                start_date,
                end_date,
                total_days,
                subtotal,
                delivery_fee,
                total_amount,
                delivery_address,
                delivery_city,
                delivery_state,
                delivery_pincode,
                order_status,
                payment_status
            FROM orders
            WHERE id = %s
              AND user_id = %s
            FOR UPDATE
        """, (
            order_id,
            session["user_id"]
        ))

        order = cursor.fetchone()

        if not order:
            return "Order not found.", 404

        order_status = order[12]
        payment_status = order[13]

        # -------------------------------------------------
        # ALREADY PAID
        # -------------------------------------------------

        if payment_status == "Paid":

            return redirect(
                url_for(
                    "order_success",
                    order_id=order_id
                )
            )

        if order_status == "Cancelled":

            return redirect(
                url_for("cart")
            )

        # -------------------------------------------------
        # GET ORDER ITEMS
        # -------------------------------------------------

        cursor.execute("""
            SELECT
                oi.id,
                oi.equipment_id,
                oi.package_id,
                oi.item_type,
                oi.item_name,
                oi.quantity,
                oi.unit_price,
                oi.business_id,
                COALESCE(
                    e.image,
                    p.image
                ) AS image
            FROM order_items oi

            LEFT JOIN equipment e
                ON oi.equipment_id = e.id

            LEFT JOIN packages p
                ON oi.package_id = p.id

            WHERE oi.order_id = %s

            ORDER BY oi.id
        """, (
            order_id,
        ))

        order_items = cursor.fetchall()

        if not order_items:
            return (
                "This order contains no items.",
                400
            )

        # -------------------------------------------------
        # RECHECK AVAILABILITY
        # -------------------------------------------------

        for item in order_items:

            item_type = item[3]
            item_id = item[1] if item_type == "Equipment" else item[2]
            quantity = int(item[5])

            if item_type == "Equipment":

                cursor.execute("""
                    SELECT
                        total_quantity,
                        is_active
                    FROM equipment
                    WHERE id = %s
                    FOR UPDATE
                """, (
                    item_id,
                ))

                equipment = cursor.fetchone()

                if not equipment or not equipment[1]:

                    return (
                        f'"{item[4]}" is no longer available.',
                        400
                    )

                total_quantity = int(
                    equipment[0]
                )

                available = (
                    get_equipment_available_quantity(
                        cursor,
                        item_id,
                        order[2],
                        order[3]
                    )
                )

                if quantity > available:

                    return (
                        f'"{item[4]}" is no longer '
                        f'available in the requested quantity.',
                        400
                    )

            else:

                package_data = get_package_availability(
                    cursor,
                    item_id,
                    order[2],
                    order[3]
                )

                if not package_data:

                    return (
                        f'"{item[4]}" is no longer available.',
                        400
                    )

                if quantity > int(
                    package_data["available_packages"]
                ):

                    return (
                        f'"{item[4]}" is no longer '
                        f'available in the requested quantity.',
                        400
                    )

        # -------------------------------------------------
        # EXISTING PENDING PAYMENT
        # -------------------------------------------------

        cursor.execute("""
            SELECT
                id,
                gateway_order_id,
                amount
            FROM payments
            WHERE order_id = %s
              AND gateway = 'Razorpay'
              AND payment_status = 'Pending'
            ORDER BY id DESC
            LIMIT 1
        """, (
            order_id,
        ))

        pending_payment = cursor.fetchone()

        if pending_payment:

            razorpay_order = {
                "id": pending_payment[1],
                "amount": int(
                    round(
                        float(
                            pending_payment[2]
                        ) * 100
                    )
                ),
                "currency": "INR"
            }

        else:

            amount_paise = int(
                round(
                    float(order[7]) * 100
                )
            )

            razorpay_order = (
                razorpay_client.order.create({
                    "amount": amount_paise,
                    "currency": "INR",
                    "payment_capture": 1
                })
            )
            
            
            cursor.execute("""
                INSERT INTO payments (
                    booking_id,
                    order_id,
                    gateway,
                    gateway_order_id,
                    amount,
                    currency,
                    payment_status
                )
                VALUES (
                    NULL,
                    %s,
                    'Razorpay',
                    %s,
                    %s,
                    'INR',
                    'Pending'
                )
            """, (
                order_id,
                razorpay_order["id"],
                order[7]
            ))

            mysql.connection.commit()

        return render_template(
            "order_payment.html",
            order=order,
            order_items=order_items,
            razorpay_order=razorpay_order,
            razorpay_key=RAZORPAY_KEY_ID
        )

    except Exception as e:

        mysql.connection.rollback()

        print(
            "Order payment page error:",
            e
        )

        return (
            "Unable to load the payment page.",
            500
        )

    finally:

        cursor.close()


def confirm_order_payment(
    cursor,
    order_id,
    user_id,
    payment_id,
    server_order_id
):
    
    # =================================================
    # LOCK ORDER
    # =================================================

    cursor.execute("""
        SELECT payment_status
        FROM orders
        WHERE id = %s
          AND user_id = %s
        FOR UPDATE
    """, (
        order_id,
        user_id
    ))

    order_status = cursor.fetchone()

    if not order_status:
        raise ValueError("Order not found.")

    # If another payment path already confirmed this order,
    # there is nothing more to do.
    if order_status[0] == "Paid":
        return True
    
    # =================================================
    # GET ORDER DATES
    # =================================================

    cursor.execute("""
        SELECT start_date, end_date
        FROM orders
        WHERE id = %s
        AND user_id = %s
        FOR UPDATE
    """, (
        order_id,
        user_id
    ))

    order_dates = cursor.fetchone()

    if not order_dates:
        raise ValueError("Order not found.")

    start_date = order_dates[0]
    end_date = order_dates[1]
    # =================================================
    # GET BOOKINGS
    # =================================================

    cursor.execute("""
        SELECT
            b.id,
            b.equipment_id,
            b.package_id,
            b.quantity,
            b.start_date,
            b.end_date,
            b.total_amount,
            b.booking_status,
            b.payment_status
        FROM bookings b
        WHERE b.order_id = %s
            AND b.user_id = %s
        ORDER BY b.id
        FOR UPDATE
    """, (
        order_id,
        user_id
    ))

    bookings = cursor.fetchall()

    if not bookings:

        raise ValueError("Order bookings not found.")

    # =================================================
    # FINAL COMBINED AVAILABILITY CHECK
    # =================================================

    payment_validation_items = []

    for booking in bookings:

        booking_id = booking[0]
        equipment_id = booking[1]
        package_id = booking[2]
        quantity = int(booking[3])

        if package_id:

            payment_validation_items.append({
                "type": "Package",
                "id": int(package_id),
                "quantity": quantity
            })

        elif equipment_id:

            payment_validation_items.append({
                "type": "Equipment",
                "id": int(equipment_id),
                "quantity": quantity
            })

        else:

            raise ValueError(
                "Invalid booking inventory."
            )


    combined_inventory_result = validate_combined_inventory(
        cursor,
        payment_validation_items,
        start_date,
        end_date
    )

    if not combined_inventory_result["success"]:

        raise ValueError(
            combined_inventory_result["message"]
        )

    # =================================================
    # CALCULATE PAYOUTS
    # =================================================

    for booking in bookings:

        booking_id = booking[0]

        booking_amount = float(
            booking[6]
        )

        commission = round(
            booking_amount
            * PLATFORM_COMMISSION_RATE,
            2
        )

        business_amount = round(
            booking_amount - commission,
            2
        )

        cursor.execute("""
            INSERT INTO payouts (
                booking_id,
                business_id,
                gross_amount,
                commission_amount,
                amount,
                currency,
                payout_status
            )
            SELECT
                b.id,
                COALESCE(
                    e.business_id,
                    p.business_id
                ),
                b.total_amount,
                %s,
                %s,
                'INR',
                'Held'
            FROM bookings b
            LEFT JOIN equipment e
                ON b.equipment_id = e.id
            LEFT JOIN packages p
                ON b.package_id = p.id
            WHERE b.id = %s
            ON DUPLICATE KEY UPDATE
                booking_id = booking_id
        """, (
            commission,
            business_amount,
            booking_id
        ))

    # =================================================
    # MARK ALL BOOKINGS PAID
    # =================================================

    cursor.execute("""
        UPDATE bookings
        SET
            payment_status = 'Paid',
            booking_status = 'Confirmed'
        WHERE order_id = %s
            AND user_id = %s
    """, (
        order_id,
        user_id
    ))

    # =================================================
    # MARK ORDER PAID
    # =================================================

    cursor.execute("""
        UPDATE orders
        SET
            payment_status = 'Paid',
            order_status = 'Confirmed'
        WHERE id = %s
            AND user_id = %s
    """, (
        order_id,
        user_id
    ))

    # =================================================
    # MARK PAYMENT PAID
    # =================================================

    cursor.execute("""
        UPDATE payments
        SET
            gateway_payment_id = %s,
            payment_status = 'Paid',
            paid_at = NOW()
        WHERE order_id = %s
            AND gateway_order_id = %s
            AND payment_status = 'Pending'
    """, (
        payment_id,
        order_id,
        server_order_id
    ))

    # =================================================
    # CLEAR CART
    # =================================================

   

    # =================================================
    # CONFIRMATION NOTIFICATION
    # =================================================

    create_notification(
        user_id,
        "order_confirmed",
        "Rental Order Confirmed",
        (
            f"Your RentEZ order #{order_id} "
            "has been confirmed successfully."
        ),
        url_for(
            "order_success",
            order_id=order_id
        )
    )

    # =================================================
    # COMMIT ORDER + PAYMENT + BOOKINGS +
    # PAYOUTS + NOTIFICATION TOGETHER
    # =================================================

    mysql.connection.commit()
    return True

@app.route(
    "/order-payment-success",
    methods=["POST"]
)
def order_payment_success():

    if not customer_logged_in():
        return jsonify({
            "success": False,
            "message": "Please login again."
        }), 401

    data = request.get_json() or {}

    try:
        order_id = int(
            data.get("order_id")
        )
    except (TypeError, ValueError):
        return jsonify({
            "success": False,
            "message": "Invalid order."
        }), 400

    payment_id = str(
        data.get(
            "razorpay_payment_id",
            ""
        )
    )

    razorpay_order_id = str(
        data.get(
            "razorpay_order_id",
            ""
        )
    )

    signature = str(
        data.get(
            "razorpay_signature",
            ""
        )
    )

    if not all([
        payment_id,
        razorpay_order_id,
        signature
    ]):
        return jsonify({
            "success": False,
            "message": "Invalid payment data."
        }), 400

    cursor = mysql.connection.cursor()

    try:

        # =================================================
        # LOCK ORDER
        # =================================================

        cursor.execute("""
            SELECT
                id,
                user_id,
                total_amount,
                payment_status,
                order_status,
                start_date,
                end_date
            FROM orders
            WHERE id = %s
            AND user_id = %s
            FOR UPDATE
        """, (
            order_id,
            session["user_id"]
        ))

        order = cursor.fetchone()

        if not order:

            return jsonify({
                "success": False,
                "message": "Order not found."
            }), 404

        # -------------------------------------------------
        # ALREADY PAID
        # -------------------------------------------------

        if order[3] == "Paid":

            return jsonify({
                "success": True,
                "redirect": url_for(
                    "order_success",
                    order_id=order_id
                )
            })

        # =================================================
        # VERIFY PAYMENT RECORD
        # =================================================

        cursor.execute("""
            SELECT
                id,
                gateway_order_id,
                amount
            FROM payments
            WHERE order_id = %s
              AND gateway = 'Razorpay'
              AND payment_status = 'Pending'
            ORDER BY id DESC
            LIMIT 1
            FOR UPDATE
        """, (
            order_id,
        ))

        payment_record = cursor.fetchone()

        if not payment_record:

            return jsonify({
                "success": False,
                "message": "Payment record not found."
            }), 400

        server_order_id = str(
            payment_record[1]
        )

        if razorpay_order_id != server_order_id:

            return jsonify({
                "success": False,
                "message": "Invalid payment order."
            }), 400

        # =================================================
        # VERIFY SIGNATURE
        # =================================================

        signature_message = (
            server_order_id
            + "|"
            + payment_id
        )

        expected_signature = hmac.new(
            RAZORPAY_KEY_SECRET.encode("utf-8"),
            signature_message.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(
            expected_signature,
            signature
        ):

            return jsonify({
                "success": False,
                "message": "Payment verification failed."
            }), 400

        confirm_order_payment(
            cursor,
            order_id,
            session["user_id"],
            payment_id,
            server_order_id
        )

        clear_cart()
        

        # =================================================
        # PREPARE CONFIRMATION EMAILS
        # =================================================

        email_tasks = []

        try:

            # -------------------------------------------------
            # CUSTOMER EMAIL
            # -------------------------------------------------

            cursor.execute("""
                SELECT
                    u.email,
                    u.full_name,
                    o.total_amount,
                    o.start_date,
                    o.end_date
                FROM orders o

                JOIN users u
                    ON o.user_id = u.id

                WHERE o.id = %s
                AND u.id = %s
            """, (
                order_id,
                session["user_id"]
            ))

            order_customer = cursor.fetchone()


            if (
                order_customer
                and order_customer[0]
            ):

                customer_email = order_customer[0]
                customer_name = order_customer[1]
                total_amount = order_customer[2]
                start_date = order_customer[3]
                end_date = order_customer[4]


                email_tasks.append({

                    "recipient":
                        customer_email,

                    "subject":
                        f"RentEZ Order #{order_id} Confirmed",

                    "body":
                        f"""Hello {customer_name},

        Your RentEZ order #{order_id} has been confirmed successfully.

        Rental period:
        {start_date} to {end_date}

        Total paid:
        ₹{float(total_amount):.2f}

        Please check My Rentals for your order details.

        Regards,
        RentEZ Team
        """
                })


            # -------------------------------------------------
            # BUSINESS EMAILS
            # -------------------------------------------------

            cursor.execute("""
                SELECT DISTINCT
                    b.business_email,
                    b.business_name

                FROM order_items oi

                JOIN businesses b
                    ON oi.business_id = b.id

                WHERE oi.order_id = %s

                AND b.business_email IS NOT NULL

                AND b.business_email != ''
            """, (
                order_id,
            ))


            for (
                business_email,
                business_name
            ) in cursor.fetchall():

                email_tasks.append({

                    "recipient":
                        business_email,

                    "subject":
                        f"RentEZ New Order #{order_id}",

                    "body":
                        f"""Hello {business_name},

        A customer has placed RentEZ order #{order_id} containing equipment or packages from your business.

        Please open the Business Bookings page to review the order and manage delivery.

        Regards,
        RentEZ Team
        """
                })


        except Exception as email_error:

            print(
                "Order confirmation email preparation failed:",
                email_error
            )


        # =================================================
        # SEND EMAILS IN BACKGROUND
        # =================================================

        for email_task in email_tasks:

            threading.Thread(
                target=send_email,
                args=(
                    email_task["recipient"],
                    email_task["subject"],
                    email_task["body"]
                ),
                daemon=True
            ).start()


        # =================================================
        # IMMEDIATE SUCCESS RESPONSE
        # =================================================

        return jsonify({
            "success": True,
            "redirect": url_for(
                "order_success",
                order_id=order_id
            )
        })
        

    except Exception as e:

        mysql.connection.rollback()

        print(
            "Order payment verification failed:",
            e
        )

        return jsonify({
            "success": False,
            "message": (
                "Unable to verify your payment."
            )
        }), 500

    finally:

        cursor.close()
        
@app.route(
    "/order-payment-failed",
    methods=["POST"]
)
def order_payment_failed():

    if not customer_logged_in():
        return jsonify({
            "success": False,
            "message": "Unauthorized."
        }), 401

    data = request.get_json() or {}

    try:
        order_id = int(
            data.get("order_id")
        )
    except (TypeError, ValueError):

        return jsonify({
            "success": False,
            "message": "Invalid order."
        }), 400

    razorpay_order_id = str(
        data.get(
            "razorpay_order_id",
            ""
        )
    )

    if not razorpay_order_id:

        return jsonify({
            "success": False,
            "message": "Invalid payment data."
        }), 400

    cursor = mysql.connection.cursor()

    try:

        cursor.execute("""
            UPDATE payments p
            JOIN orders o
                ON p.order_id = o.id
            SET
                p.payment_status = 'Failed'
            WHERE p.order_id = %s
              AND o.user_id = %s
              AND p.gateway_order_id = %s
              AND p.payment_status = 'Pending'
        """, (
            order_id,
            session["user_id"],
            razorpay_order_id
        ))

        mysql.connection.commit()

        return jsonify({
            "success": True
        })

    except Exception as e:

        mysql.connection.rollback()

        print(
            "Order payment failure update error:",
            e
        )

        return jsonify({
            "success": False,
            "message": "Unable to update payment status."
        }), 500

    finally:

        cursor.close()
        
@app.route("/order-success/<int:order_id>")
def order_success(order_id):

    if not customer_logged_in():
        return redirect(url_for("login"))

    cursor = mysql.connection.cursor()

    try:

        cursor.execute("""
            SELECT
                id,
                start_date,
                end_date,
                total_days,
                subtotal,
                delivery_fee,
                total_amount,
                delivery_address,
                delivery_city,
                delivery_state,
                delivery_pincode,
                order_status,
                payment_status
            FROM orders
            WHERE id = %s
              AND user_id = %s
        """, (
            order_id,
            session["user_id"]
        ))

        order = cursor.fetchone()

        if not order:
            return "Order not found.", 404

        cursor.execute("""
            SELECT
                oi.item_type,
                oi.item_name,
                oi.quantity,
                oi.unit_price,
                COALESCE(
                    e.image,
                    p.image
                ) AS image
            FROM order_items oi

            LEFT JOIN equipment e
                ON oi.equipment_id = e.id

            LEFT JOIN packages p
                ON oi.package_id = p.id

            WHERE oi.order_id = %s

            ORDER BY oi.id
        """, (
            order_id,
        ))

        order_items = cursor.fetchall()

        return render_template(
            "order_success.html",
            order=order,
            order_items=order_items
        )

    finally:

        cursor.close()
        

def initiate_booking_refund(
    cursor,
    booking_id,
    payment_id,
    gateway_payment_id,
    amount
):
    """
    Creates a full Razorpay refund and returns:
    {
        success: bool,
        status: 'Refunded' | 'Refund Pending',
        refund_id: str | None,
        message: str | None
    }
    """

    amount_paise = int(
        round(float(amount) * 100)
    )

    try:

        refund = razorpay_client.payment.refund(
            gateway_payment_id,
            {
                "amount": amount_paise,
                "speed": "normal",
                "receipt": f"rentez-refund-{booking_id}",
                "notes": {
                    "booking_id": str(booking_id),
                    "reason": "Booking cancellation"
                }
            }
        )

    except Exception as e:

        print(
            "Razorpay refund initiation failed:",
            e
        )

        return {
            "success": False,
            "status": None,
            "refund_id": None,
            "message": str(e)
        }

    refund_id = refund.get("id")

    if not refund_id:

        return {
            "success": False,
            "status": None,
            "refund_id": None,
            "message": "Refund ID was not returned."
        }

    refund_status = (
        refund.get("status", "")
        .lower()
    )

    if refund_status == "failed":

        cursor.execute("""
            UPDATE payments
            SET
                payment_status = 'Refund Failed',
                gateway_refund_id = %s
            WHERE id = %s
        """, (
            refund_id,
            payment_id
        ))

        return {
            "success": False,
            "status": "Refund Failed",
            "refund_id": refund_id,
            "message": "Refund failed."
        }

    if refund_status == "processed":

        cursor.execute("""
            UPDATE payments
            SET
                payment_status = 'Refunded',
                gateway_refund_id = %s,
                refund_initiated_at = NOW(),
                refunded_at = NOW()
            WHERE id = %s
        """, (
            refund_id,
            payment_id
        ))

        return {
            "success": True,
            "status": "Refunded",
            "refund_id": refund_id,
            "message": None
        }

    cursor.execute("""
        UPDATE payments
        SET
            payment_status = 'Refund Pending',
            gateway_refund_id = %s,
            refund_initiated_at = NOW()
        WHERE id = %s
    """, (
        refund_id,
        payment_id
    ))

    return {
        "success": True,
        "status": "Refund Pending",
        "refund_id": refund_id,
        "message": None
    }

@app.route("/cancel-booking/<int:booking_id>", methods=["POST"])
def cancel_booking(booking_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    cursor = mysql.connection.cursor()

    try:

        cursor.execute("""
            SELECT
                b.id,
                b.equipment_id,
                b.quantity,
                b.booking_status,
                b.payment_status,
                u.email,
                u.full_name
            FROM bookings b
            JOIN users u
                ON b.user_id = u.id
            WHERE b.id = %s
              AND b.user_id = %s
            FOR UPDATE
        """, (
            booking_id,
            session["user_id"]
        ))

        booking = cursor.fetchone()

        if not booking:
            return "Booking not found.", 404

        booking_status = booking[3]
        payment_status = booking[4]
        
        customer_email = booking[5]
        customer_name = booking[6]

        # -------------------------
        # Already cancelled
        # -------------------------

        if booking_status == "Cancelled":
            return redirect(url_for("my_rentals"))

        # -------------------------
        # Cannot cancel after
        # delivery has started
        # -------------------------

        if booking_status == "Out for Delivery":
            return (
                "This booking cannot be cancelled because "
                "the equipment is already out for delivery.",
                400
            )

        if booking_status == "Delivered":
            return (
                "This booking cannot be cancelled because "
                "the equipment has already been delivered.",
                400
            )

        if booking_status == "Returned":
            return (
                "This booking cannot be cancelled because "
                "the equipment has already been returned.",
                400
            )

        if booking_status == "Completed":
            return (
                "Completed bookings cannot be cancelled.",
                400
            )

        # -------------------------
        # UNPAID
        # -------------------------

        if (
            booking_status == "Pending"
            and payment_status == "Pending"
        ):

            cursor.execute("""
                UPDATE bookings
                SET
                    booking_status = 'Cancelled',
                    payment_status = 'Cancelled',
                    cancelled_by = 'Customer',
                    cancellation_reason = 'Cancelled by customer'
                WHERE id = %s
                  AND user_id = %s
                  AND booking_status = 'Pending'
                  AND payment_status = 'Pending'
            """, (
                booking_id,
                session["user_id"]
            ))

            cursor.execute("""
                UPDATE payments
                SET payment_status = 'Cancelled'
                WHERE booking_id = %s
                  AND payment_status = 'Pending'
            """, (
                booking_id,
            ))
            
            cursor.execute("""
                UPDATE payouts
                SET payout_status = 'Cancelled'
                WHERE booking_id = %s
                AND payout_status = 'Held'
            """, (
                booking_id,
            ))

            create_notification(
                session["user_id"],
                "booking_cancelled",
                "Booking Cancelled",
                f"Your booking #{booking_id} has been cancelled.",
                url_for("my_rentals")
            )
            
            mysql.connection.commit()

            send_email(
                    customer_email,
                    f"RentEZ Booking #{booking_id} Cancelled",
                    f"""Hello {customer_name},

                Your RentEZ booking #{booking_id} has been cancelled.

                No payment was made for this booking.
                """
                )
            
            return redirect(url_for("my_rentals"))

        # -------------------------
        # PAID + CONFIRMED
        # -------------------------

        if (
            booking_status == "Confirmed"
            and payment_status == "Paid"
        ):

            cursor.execute("""
                SELECT
                    id,
                    gateway_payment_id,
                    amount
                FROM payments
                WHERE booking_id = %s
                  AND gateway = 'Razorpay'
                  AND payment_status = 'Paid'
                  AND gateway_payment_id IS NOT NULL
                ORDER BY id DESC
                LIMIT 1
                FOR UPDATE
            """, (
                booking_id,
            ))

            payment = cursor.fetchone()

            if not payment:
                return (
                    "Original payment could not be found.",
                    400
                )

            payment_id = payment[0]
            gateway_payment_id = str(payment[1])
            payment_amount = payment[2]

            refund_result = initiate_booking_refund(
                cursor,
                booking_id,
                payment_id,
                gateway_payment_id,
                payment_amount
            )

            # Refund itself failed
            if not refund_result["success"]:

                if refund_result["status"] == "Refund Failed":

                    mysql.connection.commit()

                    return (
                        "The refund failed. "
                        "Your booking remains confirmed. "
                        "Please try again or contact support.",
                        400
                    )

                mysql.connection.rollback()

                return (
                    "Refund could not be initiated. "
                    "Your booking is still confirmed.",
                    400
                )

            # Successful refund initiation
            cursor.execute("""
                UPDATE bookings
                SET
                    booking_status = 'Cancelled',
                    payment_status = %s,
                    cancelled_by = 'Customer',
                    cancellation_reason = %s
                WHERE id = %s
                  AND user_id = %s
                  AND booking_status = 'Confirmed'
                  AND payment_status = 'Paid'
            """, (
                refund_result["status"],
                "Cancelled by customer",
                booking_id,
                session["user_id"]
            ))

            # Payout must not be released after customer cancellation
            cursor.execute("""
                UPDATE payouts
                SET payout_status = 'Cancelled'
                WHERE booking_id = %s
                  AND payout_status = 'Held'
            """, (
                booking_id,
            ))

            create_notification(
                session["user_id"],
                "booking_cancelled",
                "Booking Cancelled",
                (
                    f"Your booking #{booking_id} has been cancelled. "
                    f"Your refund status is now "
                    f"{refund_result['status']}."
                ),
                url_for("my_rentals")
            )

            mysql.connection.commit()

            send_email(
                customer_email,
                f"RentEZ Booking #{booking_id} Cancelled",
                f"""Hello {customer_name},

                Your RentEZ booking #{booking_id} has been cancelled.

                Refund status:
                {refund_result['status']}

                Please check My Rentals for the latest information.
                """
            )

            return redirect(
                url_for("my_rentals")
            )


        return (
            "This booking cannot be cancelled in its current state.",
            400
        )

    except Exception as e:

        mysql.connection.rollback()

        print(
            "Booking cancellation failed:",
            e
        )

        return "Unable to cancel booking.", 500

    finally:
        cursor.close()
        

        
@app.route(
    "/razorpay-webhook",
    methods=["POST"]
)
def razorpay_webhook():

    webhook_secret = os.getenv(
        "RAZORPAY_WEBHOOK_SECRET"
    )

    if not webhook_secret:
        return (
            "Webhook secret not configured.",
            500
        )

    raw_body = request.get_data()

    received_signature = (
        request.headers.get(
            "X-Razorpay-Signature"
        )
    )

    if not received_signature:
        return "Missing signature.", 400

    expected_signature = hmac.new(
        webhook_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(
        expected_signature,
        received_signature
    ):
        return "Invalid signature.", 400

    data = request.get_json(
        silent=True
    )

    if not data:
        return "Invalid payload.", 400

    event = data.get("event")

    if event == "payment.captured":

        payment_entity = (
            data
            .get("payload", {})
            .get("payment", {})
            .get("entity", {})
        )

        gateway_payment_id = payment_entity.get("id")
        gateway_order_id = payment_entity.get("order_id")

        if not gateway_payment_id or not gateway_order_id:
            return "Invalid payment payload.", 400

        cursor = mysql.connection.cursor()

        try:

            cursor.execute("""
                SELECT
                    p.order_id,
                    p.amount,
                    p.payment_status,
                    o.user_id
                FROM payments p
                JOIN orders o
                    ON p.order_id = o.id
                WHERE p.gateway = 'Razorpay'
                AND p.gateway_order_id = %s
                AND p.order_id IS NOT NULL
                LIMIT 1
            """, (
                str(gateway_order_id),
            ))

            payment_row = cursor.fetchone()

            if not payment_row:
                return jsonify({
                    "success": True
                })

            order_id = payment_row[0]
            expected_amount = float(payment_row[1])
            current_status = payment_row[2]
            user_id = payment_row[3]

            webhook_amount = (
                float(
                    payment_entity.get(
                        "amount",
                        0
                    )
                ) / 100
            )

            if abs(
                webhook_amount - expected_amount
            ) > 0.01:

                mysql.connection.rollback()

                return (
                    "Payment amount mismatch.",
                    400
                )

            # Browser callback already completed it.
            if current_status == "Paid":

                mysql.connection.commit()

                return jsonify({
                    "success": True
                })

            confirm_order_payment(
                cursor,
                order_id,
                user_id,
                gateway_payment_id,
                str(gateway_order_id)
            )

            return jsonify({
                "success": True
            })

        except Exception as e:

            mysql.connection.rollback()

            print(
                "Payment webhook failed:",
                e
            )

            return jsonify({
                "success": False
            }), 500

        finally:

            cursor.close()

    if event not in {
    "payment.captured",
    "refund.processed",
    "refund.failed"
    }:
        return jsonify({
            "success": True
        })

    refund_entity = (
        data
        .get("payload", {})
        .get("refund", {})
        .get("entity", {})
    )

    gateway_refund_id = (
        refund_entity.get("id")
    )

    gateway_payment_id = (
        refund_entity.get("payment_id")
    )

    if (
        not gateway_refund_id
        or not gateway_payment_id
    ):
        return "Invalid refund payload.", 400

    cursor = mysql.connection.cursor()

    try:

        cursor.execute("""
            SELECT
                pr.id,
                pr.payment_id,
                pr.order_id,
                pr.booking_id,
                pr.status,
                o.user_id,
                u.email,
                u.full_name

            FROM payment_refunds pr

            JOIN payments p
                ON pr.payment_id = p.id

            JOIN orders o
                ON pr.order_id = o.id

            JOIN users u
                ON o.user_id = u.id

            WHERE pr.gateway_refund_id = %s
              AND p.gateway_payment_id = %s

            FOR UPDATE
        """, (
            str(gateway_refund_id),
            str(gateway_payment_id)
        ))

        refund_row = cursor.fetchone()

        if not refund_row:

            return jsonify({
                "success": True
            })

        (
            refund_db_id,
            payment_id,
            order_id,
            booking_id,
            previous_refund_status,
            customer_user_id,
            customer_email,
            customer_name
        ) = refund_row

        new_refund_status = (
            "Processed"
            if event == "refund.processed"
            else "Failed"
        )

        cursor.execute("""
            UPDATE payment_refunds

            SET
                status = %s,

                processed_at = CASE
                    WHEN %s = 'Processed'
                    THEN COALESCE(
                        processed_at,
                        NOW()
                    )
                    ELSE processed_at
                END

            WHERE id = %s
        """, (
            new_refund_status,
            new_refund_status,
            refund_db_id
        ))

        if booking_id is not None:

            booking_payment_status = (
                "Refunded"
                if new_refund_status == "Processed"
                else "Refund Failed"
            )

            cursor.execute("""
                UPDATE bookings

                SET payment_status = %s

                WHERE id = %s
                  AND booking_status = 'Cancelled'
            """, (
                booking_payment_status,
                booking_id
            ))

        order_state = (
            recalculate_order_refund_state(
                cursor,
                order_id
            )
        )

        if not order_state:

            mysql.connection.rollback()

            return (
                "Order not found.",
                400
            )

        if (
            order_state["payment_status"]
            == "Refunded"
        ):

            cursor.execute("""
                UPDATE payments
                SET
                    payment_status = 'Refunded',
                    refunded_at =
                        COALESCE(
                            refunded_at,
                            NOW()
                        )

                WHERE id = %s
            """, (
                payment_id,
            ))

        elif (
            order_state["payment_status"]
            == "Refund Failed"
        ):

            cursor.execute("""
                UPDATE payments
                SET payment_status = 'Refund Failed'
                WHERE id = %s
            """, (
                payment_id,
            ))

        elif (
            order_state["payment_status"]
            == "Refund Pending"
        ):

            cursor.execute("""
                UPDATE payments
                SET payment_status = 'Refund Pending'
                WHERE id = %s
            """, (
                payment_id,
            ))

        else:

            cursor.execute("""
                UPDATE payments
                SET payment_status = 'Paid'
                WHERE id = %s
            """, (
                payment_id,
            ))

        if previous_refund_status == "Pending":

            if new_refund_status == "Processed":

                notification_type = (
                    "refund_completed"
                )

                title = "Refund Completed"

                message = (
                    f"Your refund for order "
                    f"#{order_id} has been completed "
                    "successfully."
                )

            else:

                notification_type = (
                    "refund_failed"
                )

                title = "Refund Failed"

                message = (
                    f"Your refund for order "
                    f"#{order_id} could not be "
                    "completed. Please contact "
                    "RentEZ support."
                )

            create_notification(
                customer_user_id,
                notification_type,
                title,
                message,
                url_for("my_rentals")
            )

        mysql.connection.commit()

        if (
            previous_refund_status
            == "Pending"
            and customer_email
        ):

            if new_refund_status == "Processed":

                subject = (
                    f"RentEZ Refund Completed - "
                    f"Order #{order_id}"
                )

                body = f"""Hello {customer_name},

A refund associated with RentEZ order #{order_id} has been completed successfully.

Please check My Rentals for the latest order information.

Regards,
RentEZ Team
"""

            else:

                subject = (
                    f"RentEZ Refund Update - "
                    f"Order #{order_id}"
                )

                body = f"""Hello {customer_name},

A refund associated with RentEZ order #{order_id} could not be completed.

Please contact RentEZ support for assistance.

Regards,
RentEZ Team
"""

            send_email(
                customer_email,
                subject,
                body
            )

        return jsonify({
            "success": True
        })

    except Exception as e:

        mysql.connection.rollback()

        print(
            "Razorpay webhook failed:",
            e
        )

        return jsonify({
            "success": False,
            "message":
                "Webhook processing failed."
        }), 500

    finally:

        cursor.close()
        


@app.route(
    "/check-order-refund-status/<int:order_id>"
)
def check_order_refund_status(order_id):

    if not customer_logged_in():

        return jsonify({
            "success": False,
            "message": "Unauthorized."
        }), 401

    cursor = mysql.connection.cursor()

    try:

        cursor.execute("""
            SELECT
                pr.id,
                pr.gateway_refund_id,
                pr.booking_id,
                pr.status

            FROM payment_refunds pr

            JOIN orders o
                ON pr.order_id = o.id

            WHERE pr.order_id = %s
              AND o.user_id = %s
              AND pr.status = 'Pending'

            ORDER BY pr.id ASC
        """, (
            order_id,
            session["user_id"]
        ))

        pending_refunds = cursor.fetchall()


        for refund_row in pending_refunds:

            refund_db_id = refund_row[0]
            refund_id = str(
                refund_row[1]
            )

            booking_id = refund_row[2]

            try:

                refund = (
                    razorpay_client.refund.fetch(
                        refund_id
                    )
                )

            except Exception as e:

                print(
                    f"Refund {refund_id} "
                    f"check failed:",
                    e
                )

                continue


            gateway_status = str(
                refund.get(
                    "status",
                    ""
                )
            ).lower().strip()


            if gateway_status == "processed":

                cursor.execute("""
                    UPDATE payment_refunds

                    SET
                        status = 'Processed',
                        processed_at =
                            COALESCE(
                                processed_at,
                                NOW()
                            )

                    WHERE id = %s
                """, (
                    refund_db_id,
                ))


                if booking_id is not None:

                    cursor.execute("""
                        UPDATE bookings

                        SET payment_status =
                            'Refunded'

                        WHERE id = %s
                          AND booking_status =
                              'Cancelled'
                    """, (
                        booking_id,
                    ))


            elif gateway_status in (
                "failed",
                "rejected"
            ):

                cursor.execute("""
                    UPDATE payment_refunds

                    SET status = 'Failed'

                    WHERE id = %s
                """, (
                    refund_db_id,
                ))


                if booking_id is not None:

                    cursor.execute("""
                        UPDATE bookings

                        SET payment_status =
                            'Refund Failed'

                        WHERE id = %s
                          AND booking_status =
                              'Cancelled'
                    """, (
                        booking_id,
                    ))


        # -----------------------------------------------------
        # Recalculate order after all refunds are checked
        # -----------------------------------------------------

        state = (
            recalculate_order_refund_state(
                cursor,
                order_id
            )
        )


        if not state:

            mysql.connection.rollback()

            return jsonify({
                "success": False,
                "message": "Order not found."
            }), 404


        # -----------------------------------------------------
        # Sync payment row with order state
        # -----------------------------------------------------

        cursor.execute("""
            UPDATE payments

            SET payment_status = %s

            WHERE order_id = %s
        """, (
            state["payment_status"],
            order_id
        ))


        mysql.connection.commit()


        return jsonify({
            "success": True,
            "status":
                state["payment_status"]
        })


    except Exception as e:

        mysql.connection.rollback()

        print(
            "Order refund status check failed:",
            e
        )

        return jsonify({
            "success": False,
            "message":
                "Unable to check refund status."
        }), 500

    finally:

        cursor.close()
    
    
# =========================================================
# CUSTOMER BUSINESS-LEVEL RENTAL STATUS
# =========================================================

def get_customer_business_status(
    booking_statuses
):

    statuses = set(
        booking_statuses
    )

    if not statuses:
        return "Pending"

    # All bookings for this business are cancelled
    if statuses == {"Cancelled"}:
        return "Cancelled"

    # Some bookings cancelled, some still active
    if "Cancelled" in statuses:
        return "Partially Cancelled"

    # All completed
    if statuses == {"Completed"}:
        return "Completed"

    # Rental is currently active
    if (
        "Delivered" in statuses
        or "Returned" in statuses
    ):
        return "Active Rental"

    if "Out for Delivery" in statuses:
        return "Out for Delivery"

    if "Confirmed" in statuses:
        return "Confirmed"

    return "Pending"

def get_customer_rental_status(
    booking_statuses
):

    statuses = set(
        booking_statuses
    )

    if not statuses:
        return "Pending"

    if statuses == {"Cancelled"}:
        return "Cancelled"

    if statuses == {"Completed"}:
        return "Completed"

    if (
        "Delivered" in statuses
        or "Returned" in statuses
    ):
        return "Active Rental"

    if "Out for Delivery" in statuses:
        return "Out for Delivery"

    if "Confirmed" in statuses:
        return "Confirmed"

    return "Pending"


@app.route("/my-rentals")
def my_rentals():

    if "user_id" not in session:
        return redirect(url_for("login"))

    cursor = mysql.connection.cursor()

    try:

        cursor.execute("""
            SELECT
                b.id,
                b.order_id,
                b.start_date,
                b.end_date,
                b.total_days,
                b.daily_rate,
                b.total_amount,
                b.booking_status,
                b.payment_status,
                b.quantity,

                COALESCE(
                    e.id,
                    pkg.id
                ) AS item_id,

                COALESCE(
                    e.name,
                    pkg.name
                ) AS item_name,

                CASE
                    WHEN b.package_id IS NOT NULL
                    THEN 'Rental Package'
                    ELSE e.category
                END AS category,

                COALESCE(
                    e.image,
                    pkg.image
                ) AS image,

                b.package_id,

                biz.id AS business_id,

                biz.business_name AS business_name,

                o.total_amount AS order_total,
                o.delivery_address AS order_address,
                o.delivery_city AS order_city,
                o.delivery_state AS order_state,
                o.delivery_pincode AS order_pincode,
                o.payment_status AS order_payment_status,
                o.order_status AS order_status

            FROM bookings b

            LEFT JOIN equipment e
                ON b.equipment_id = e.id

            LEFT JOIN packages pkg
                ON b.package_id = pkg.id

            LEFT JOIN businesses biz
                ON biz.id = COALESCE(
                    e.business_id,
                    pkg.business_id
                )

            LEFT JOIN orders o
                ON b.order_id = o.id

            WHERE b.user_id = %s

            ORDER BY
                COALESCE(
                    b.order_id,
                    b.id
                ) DESC,

                b.id DESC
        """, (
            session["user_id"],
        ))

        rows = cursor.fetchall()


        # =================================================
        # GROUP BOOKINGS INTO ORDERS
        # =================================================

        grouped = {}


        for row in rows:

            booking_id = row[0]
            order_id = row[1]

            # Legacy booking without an order
            group_key = (
                f"order-{order_id}"
                if order_id is not None
                else f"booking-{booking_id}"
            )


            if group_key not in grouped:

                grouped[group_key] = {

                    "order_id": order_id,

                    "display_id": (
                        order_id
                        if order_id is not None
                        else booking_id
                    ),

                    "is_order":
                        order_id is not None,

                    "start_date": row[2],
                    "end_date": row[3],
                    "total_days": row[4],

                    # Keeps existing order cancellation
                    # logic working internally.
                    "status": None,

                    "payment_status": (

                        row[22]
                        if order_id is not None
                        and row[22]
                        else row[8]

                    ),

                    "total": (

                        float(row[17])
                        if order_id is not None
                        and row[17] is not None
                        else 0

                    ),

                    "address": row[18],
                    "city": row[19],
                    "state": row[20],
                    "pincode": row[21],

                    "items": [],

                    # NEW:
                    # Separate businesses inside this order.
                    "businesses": []

                }


            group = grouped[group_key]


            # =================================================
            # ADD ITEM
            # =================================================

            item = {

                "booking_id": row[0],

                "quantity":
                    row[9]
                    if row[9] is not None
                    else 1,

                "name": row[11],

                "category": row[12],

                "image": row[13],

                "is_package":
                    row[14] is not None,

                "total_amount":
                    float(row[6]),

                "daily_rate":
                    float(row[5]),

                "booking_status":
                    row[7],

                "payment_status":
                    row[8]

            }


            group["items"].append(item)


            # =================================================
            # FIND BUSINESS GROUP
            # =================================================

            business_id = row[15]

            business_name = (
                row[16]
                if row[16]
                else "Rental Business"
            )


            business_key = (

                f"business-{business_id}"

                if business_id is not None

                else f"business-booking-{booking_id}"

            )


            business_group = None


            for existing_business in group["businesses"]:

                if existing_business["key"] == business_key:

                    business_group = existing_business

                    break


            if business_group is None:

                business_group = {

                    "key": business_key,

                    "business_id": business_id,

                    "business_name": business_name,

                    "items": [],

                    "status": None

                }

                group["businesses"].append(
                    business_group
                )


            business_group["items"].append(
                item
            )


            # Legacy booking total
            if not group["is_order"]:

                group["total"] = float(
                    row[6]
                )


        rentals = list(
            grouped.values()
        )


        # =================================================
        # CALCULATE STATUS
        # =================================================

        for rental in rentals:

            all_statuses = []


            for business in rental["businesses"]:

                business_statuses = [

                    item["booking_status"]

                    for item in business["items"]

                ]


                business["status"] = (
                    get_customer_business_status(
                        business_statuses
                    )
                )


                all_statuses.extend(
                    business_statuses
                )


            # Keep existing order-level status
            # internally for existing order actions.
            rental["status"] = (
                get_customer_rental_status(
                    all_statuses
                )
                if all_statuses
                else "Pending"
            )


        return render_template(
            "my_rentals.html",
            rentals=rentals,
            user_name=session["user_name"]
        )


    finally:

        cursor.close()
    
@app.route("/business-login", methods=["GET", "POST"])
def business_login():

    if request.method == "GET":
        return render_template(
            "business_login.html"
        )

    email = request.form.get(
        "email",
        ""
    ).strip().lower()

    password = request.form.get(
        "password",
        ""
    )

    if not email or not password:

        return render_template(
            "business_login.html",
            login_type="error",
            login_title="Missing information",
            login_message=(
                "Please enter your email address and password."
            )
        )

    cursor = mysql.connection.cursor()

    try:

        cursor.execute("""
            SELECT
                u.id,
                u.full_name,
                u.email,
                u.password,
                u.user_type,
                b.id,
                b.business_name,
                b.approval_status,
                b.rejection_reason
            FROM users u
            LEFT JOIN businesses b
                ON b.user_id = u.id
            WHERE u.email = %s
              AND u.user_type = 'Business'
        """, (email,))

        user = cursor.fetchone()

    finally:
        cursor.close()

    if not user:

        return render_template(
            "business_login.html",
            login_type="error",
            login_title="Login failed",
            login_message=(
                "Invalid business email or password."
            )
        )

    user_id = user[0]
    full_name = user[1]
    stored_password = user[3]

    business_id = user[5]
    approval_status = user[7]

    if not check_password_hash(
        stored_password,
        password
    ):

        return render_template(
            "business_login.html",
            login_type="error",
            login_title="Login failed",
            login_message=(
                "Invalid business email or password."
            )
        )

    if not business_id:

        return render_template(
            "business_login.html",
            login_type="error",
            login_title="Unable to login",
            login_message=(
                "Your business account could not be found. "
                "Please contact RentEZ support."
            )
        )

    # =====================================================
    # CREATE BUSINESS SESSION
    # =====================================================

    session.clear()

    session.permanent = True

    session["user_id"] = user_id
    session["user_name"] = full_name.split()[0]
    session["user_type"] = "Business"
    session["business_id"] = business_id

    # =====================================================
    # APPROVED
    # =====================================================

    if approval_status == "Approved":

        return redirect(
            url_for("business_dashboard")
        )

    # =====================================================
    # PENDING / REJECTED
    # =====================================================

    return redirect(
        url_for("business_status")
    )

@app.after_request
def add_no_cache_headers(response):

    if request.endpoint in {
        "login",
        "business_login",
        "admin_login"
    }:

        response.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, max-age=0"
        )

        response.headers["Pragma"] = "no-cache"

        response.headers["Expires"] = "0"

    return response


@app.route("/business-status")
def business_status():

    if (
        "user_id" not in session
        or session.get("user_type") != "Business"
        or "business_id" not in session
    ):
        return redirect(url_for("business_login"))

    business_id = session["business_id"]
    user_id = session["user_id"]

    cursor = mysql.connection.cursor()

    try:

        cursor.execute("""
            SELECT
                b.id,
                b.business_name,
                b.approval_status,
                b.rejection_reason,
                b.registration_number,
                b.city
            FROM businesses b
            WHERE b.id = %s
              AND b.user_id = %s
        """, (
            business_id,
            user_id
        ))

        business = cursor.fetchone()

        if not business:
            session.clear()
            return redirect(url_for("business_login"))

        return render_template(
            "business_status.html",
            business=business
        )

    finally:
        cursor.close()
        

# =========================================================
# BUSINESS PACKAGE MANAGEMENT
# =========================================================

@app.route("/business/packages")
def business_packages():

    if (
        "user_id" not in session
        or session.get("user_type") != "Business"
        or "business_id" not in session
    ):
        return redirect(url_for("business_login"))

    business_id = session["business_id"]

    cursor = mysql.connection.cursor()

    try:

        cursor.execute("""
            SELECT
                p.id,
                p.name,
                p.description,
                p.image,
                p.price_per_day,
                p.is_active,
                p.created_at,
                COUNT(pi.id)
            FROM packages p
            LEFT JOIN package_items pi
                ON pi.package_id = p.id
            WHERE p.business_id = %s
            GROUP BY
                p.id,
                p.name,
                p.description,
                p.image,
                p.price_per_day,
                p.is_active,
                p.created_at
            ORDER BY p.created_at DESC
        """, (
            business_id,
        ))

        packages = cursor.fetchall()

        return render_template(
            "business_packages.html",
            packages=packages
        )

    finally:
        cursor.close()


@app.route(
    "/business/packages/create",
    methods=["GET", "POST"]
)
def create_business_package():

    if (
        "user_id" not in session
        or session.get("user_type") != "Business"
        or "business_id" not in session
    ):
        return redirect(url_for("business_login"))

    business_id = session["business_id"]

    cursor = mysql.connection.cursor()

    try:

        cursor.execute("""
            SELECT
                id,
                name,
                price_per_day,
                total_quantity,
                available_quantity,
                is_active
            FROM equipment
            WHERE business_id = %s
              AND is_active = TRUE
            ORDER BY name ASC
        """, (
            business_id,
        ))

        equipment = cursor.fetchall()

        if request.method == "GET":

            return render_template(
                "business_create_package.html",
                package=None,
                equipment=equipment,
                selected_items={}
            )

        name = request.form.get(
            "name",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        price_per_day = request.form.get(
            "price_per_day",
            ""
        ).strip()

        if not name:

            return render_template(
                "business_create_package.html",
                package=None,
                equipment=equipment,
                selected_items={},
                error="Package name is required."
            )

        try:

            price_per_day = float(
                price_per_day
            )

        except (ValueError, TypeError):

            return render_template(
                "business_create_package.html",
                package=None,
                equipment=equipment,
                selected_items={},
                error="Enter a valid package price."
            )

        if price_per_day <= 0:

            return render_template(
                "business_create_package.html",
                package=None,
                equipment=equipment,
                selected_items={},
                error="Package price must be greater than zero."
            )

        # -------------------------------------------------
        # COLLECT COMPONENTS
        # -------------------------------------------------

        selected_items = {}

        for item in equipment:

            equipment_id = item[0]

            raw_quantity = request.form.get(
                f"quantity_{equipment_id}",
                ""
            ).strip()

            if not raw_quantity:
                continue

            try:
                quantity = int(raw_quantity)
            except ValueError:
                continue

            if quantity < 1:
                continue

            if quantity > int(item[3]):

                return render_template(
                    "business_create_package.html",
                    package=None,
                    equipment=equipment,
                    selected_items=selected_items,
                    error=(
                        f'You cannot add more than '
                        f'{item[3]} unit(s) of "{item[1]}".'
                    )
                )

            selected_items[equipment_id] = quantity

        if not selected_items:

            return render_template(
                "business_create_package.html",
                package=None,
                equipment=equipment,
                selected_items=selected_items,
                error="Select at least one equipment item."
            )

        # -------------------------------------------------
        # IMAGE
        # -------------------------------------------------

        image = request.files.get("image")

        unique_filename = None

        if image and image.filename:

            filename = secure_filename(
                image.filename
            )

            extension = get_file_extension(
                filename
            )

            if (
                not filename
                or extension not in ALLOWED_PACKAGE_IMAGES
            ):

                return render_template(
                    "business_create_package.html",
                    package=None,
                    equipment=equipment,
                    selected_items=selected_items,
                    error=(
                        "Only JPG, JPEG, PNG and WEBP "
                        "images are allowed."
                    )
                )

            image.stream.seek(
                0,
                os.SEEK_END
            )

            image_size = image.stream.tell()

            image.stream.seek(0)

            if image_size > MAX_PACKAGE_IMAGE_SIZE:

                return render_template(
                    "business_create_package.html",
                    package=None,
                    equipment=equipment,
                    selected_items=selected_items,
                    error="Package image must be 5 MB or smaller."
                )

            if not valid_file_signature(
                image,
                extension
            ):

                return render_template(
                    "business_create_package.html",
                    package=None,
                    equipment=equipment,
                    selected_items=selected_items,
                    error="The uploaded package image is invalid."
                )

            unique_filename = (
                f"package_{business_id}_"
                f"{uuid.uuid4().hex}.{extension}"
            )

            image.save(
                os.path.join(
                    PACKAGE_UPLOAD_FOLDER,
                    unique_filename
                )
            )

        # -------------------------------------------------
        # CREATE PACKAGE
        # -------------------------------------------------

        cursor.execute("""
            INSERT INTO packages
            (
                business_id,
                name,
                description,
                image,
                price_per_day,
                is_active
            )
            VALUES (%s, %s, %s, %s, %s, TRUE)
        """, (
            business_id,
            name,
            description,
            unique_filename,
            price_per_day
        ))

        package_id = cursor.lastrowid

        for equipment_id, quantity in selected_items.items():

            cursor.execute("""
                INSERT INTO package_items
                (
                    package_id,
                    equipment_id,
                    quantity
                )
                VALUES (%s, %s, %s)
            """, (
                package_id,
                equipment_id,
                quantity
            ))

        mysql.connection.commit()

        return redirect(
            url_for("business_packages")
        )

    except Exception as e:

        mysql.connection.rollback()

        print(
            "Package creation failed:",
            e
        )

        return render_template(
            "business_create_package.html",
            package=None,
            equipment=equipment if "equipment" in locals() else [],
            selected_items={},
            error="Unable to create package."
        )

    finally:
        cursor.close()


@app.route(
    "/business/packages/<int:package_id>/edit",
    methods=["GET", "POST"]
)
def edit_business_package(package_id):

    if (
        "user_id" not in session
        or session.get("user_type") != "Business"
        or "business_id" not in session
    ):
        return redirect(url_for("business_login"))

    business_id = session["business_id"]

    cursor = mysql.connection.cursor()

    try:

        cursor.execute("""
            SELECT
                id,
                name,
                description,
                image,
                price_per_day,
                is_active
            FROM packages
            WHERE id = %s
              AND business_id = %s
        """, (
            package_id,
            business_id
        ))

        package = cursor.fetchone()

        if not package:
            return "Package not found.", 404

        cursor.execute("""
            SELECT
                id,
                name,
                price_per_day,
                total_quantity,
                available_quantity,
                is_active
            FROM equipment
            WHERE business_id = %s
              AND (
                    is_active = TRUE
                    OR id IN (
                        SELECT equipment_id
                        FROM package_items
                        WHERE package_id = %s
                    )
              )
            ORDER BY name ASC
        """, (
            business_id,
            package_id
        ))

        equipment = cursor.fetchall()

        cursor.execute("""
            SELECT
                equipment_id,
                quantity
            FROM package_items
            WHERE package_id = %s
        """, (
            package_id,
        ))

        selected_items = {
            row[0]: row[1]
            for row in cursor.fetchall()
        }

        if request.method == "GET":

            return render_template(
                "business_create_package.html",
                package=package,
                equipment=equipment,
                selected_items=selected_items
            )

        name = request.form.get(
            "name",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        price_per_day = request.form.get(
            "price_per_day",
            ""
        ).strip()

        if not name:

            return render_template(
                "business_create_package.html",
                package=package,
                equipment=equipment,
                selected_items=selected_items,
                error="Package name is required."
            )

        try:

            price_per_day = float(
                price_per_day
            )

        except (ValueError, TypeError):

            return render_template(
                "business_create_package.html",
                package=package,
                equipment=equipment,
                selected_items=selected_items,
                error="Enter a valid package price."
            )

        if price_per_day <= 0:

            return render_template(
                "business_create_package.html",
                package=package,
                equipment=equipment,
                selected_items=selected_items,
                error="Package price must be greater than zero."
            )

        new_items = {}

        for item in equipment:

            equipment_id = item[0]

            raw_quantity = request.form.get(
                f"quantity_{equipment_id}",
                ""
            ).strip()

            if not raw_quantity:
                continue

            try:
                quantity = int(raw_quantity)
            except ValueError:
                continue

            if quantity < 1:
                continue

            # Archived equipment may still be shown so
            # it can be removed from the package.
            if quantity > int(item[3]):

                return render_template(
                    "business_create_package.html",
                    package=package,
                    equipment=equipment,
                    selected_items=new_items,
                    error=(
                        f'You cannot add more than '
                        f'{item[3]} unit(s) of "{item[1]}".'
                    )
                )

            new_items[equipment_id] = quantity

        if not new_items:

            return render_template(
                "business_create_package.html",
                package=package,
                equipment=equipment,
                selected_items=new_items,
                error="A package must contain at least one equipment item."
            )

        new_image = package[3]

        image = request.files.get("image")

        if image and image.filename:

            filename = secure_filename(
                image.filename
            )

            extension = get_file_extension(
                filename
            )

            if extension not in ALLOWED_PACKAGE_IMAGES:

                return render_template(
                    "business_create_package.html",
                    package=package,
                    equipment=equipment,
                    selected_items=new_items,
                    error=(
                        "Only JPG, JPEG, PNG and WEBP "
                        "images are allowed."
                    )
                )

            image.stream.seek(
                0,
                os.SEEK_END
            )

            image_size = image.stream.tell()

            image.stream.seek(0)

            if image_size > MAX_PACKAGE_IMAGE_SIZE:

                return render_template(
                    "business_create_package.html",
                    package=package,
                    equipment=equipment,
                    selected_items=new_items,
                    error="Package image must be 5 MB or smaller."
                )

            if not valid_file_signature(
                image,
                extension
            ):

                return render_template(
                    "business_create_package.html",
                    package=package,
                    equipment=equipment,
                    selected_items=new_items,
                    error="Invalid package image."
                )

            new_image = (
                f"package_{business_id}_"
                f"{uuid.uuid4().hex}.{extension}"
            )

            image.save(
                os.path.join(
                    PACKAGE_UPLOAD_FOLDER,
                    new_image
                )
            )

            if package[3]:

                old_image = os.path.join(
                    PACKAGE_UPLOAD_FOLDER,
                    package[3]
                )

                if os.path.isfile(old_image):

                    try:
                        os.remove(old_image)
                    except OSError:
                        pass

        cursor.execute("""
            UPDATE packages
            SET
                name = %s,
                description = %s,
                image = %s,
                price_per_day = %s
            WHERE id = %s
              AND business_id = %s
        """, (
            name,
            description,
            new_image,
            price_per_day,
            package_id,
            business_id
        ))

        cursor.execute("""
            DELETE FROM package_items
            WHERE package_id = %s
        """, (
            package_id,
        ))

        for equipment_id, quantity in new_items.items():

            cursor.execute("""
                INSERT INTO package_items
                (
                    package_id,
                    equipment_id,
                    quantity
                )
                VALUES (%s, %s, %s)
            """, (
                package_id,
                equipment_id,
                quantity
            ))

        mysql.connection.commit()

        return redirect(
            url_for("business_packages")
        )

    except Exception as e:

        mysql.connection.rollback()

        print(
            "Package update failed:",
            e
        )

        return (
            "Unable to update package.",
            500
        )

    finally:
        cursor.close()


@app.route(
    "/business/packages/<int:package_id>/toggle",
    methods=["POST"]
)
def toggle_business_package(package_id):

    if (
        "user_id" not in session
        or session.get("user_type") != "Business"
        or "business_id" not in session
    ):
        return jsonify({
            "success": False,
            "message": "Please log in as a business."
        }), 401

    cursor = mysql.connection.cursor()

    try:

        cursor.execute("""
            SELECT
                id,
                name,
                is_active
            FROM packages
            WHERE id = %s
              AND business_id = %s
        """, (
            package_id,
            session["business_id"]
        ))

        package = cursor.fetchone()

        if not package:

            return jsonify({
                "success": False,
                "message": "Package not found."
            }), 404

        new_status = not bool(package[2])

        cursor.execute("""
            UPDATE packages
            SET is_active = %s
            WHERE id = %s
              AND business_id = %s
        """, (
            new_status,
            package_id,
            session["business_id"]
        ))

        mysql.connection.commit()

        return jsonify({
            "success": True,
            "active": new_status,
            "message": (
                f'"{package[1]}" has been '
                f'{"activated" if new_status else "deactivated"}.'
            )
        })

    except Exception as e:

        mysql.connection.rollback()

        print(
            "Package status update failed:",
            e
        )

        return jsonify({
            "success": False,
            "message": "Unable to update package status."
        }), 500

    finally:
        cursor.close()


@app.route("/package-image/<path:filename>")
def package_image(filename):

    return send_from_directory(
        PACKAGE_UPLOAD_FOLDER,
        filename
    )
    
    
def get_equipment_available_quantity(
    cursor,
    equipment_id,
    start_date,
    end_date,
    exclude_booking_id=None
):
    """
    Returns date-specific available quantity.

    Includes:
    - direct equipment bookings
    - equipment consumed by package bookings
    """

    cursor.execute("""
        SELECT
            total_quantity
        FROM equipment
        WHERE id = %s
          AND is_active = TRUE
    """, (
        equipment_id,
    ))

    equipment = cursor.fetchone()

    if not equipment:
        return 0

    total_quantity = int(
        equipment[0]
    )

    # =====================================================
    # DIRECT EQUIPMENT BOOKINGS
    # =====================================================

    query = """
        SELECT
            COALESCE(SUM(b.quantity), 0)

        FROM bookings b

        WHERE b.equipment_id = %s

          AND b.payment_status = 'Paid'

          AND b.booking_status IN (
              'Confirmed',
              'Out for Delivery',
              'Delivered'
          )

          AND b.start_date < %s
          AND b.end_date > %s
    """

    params = [
        equipment_id,
        end_date,
        start_date
    ]

    if exclude_booking_id is not None:

        query += """
            AND b.id != %s
        """

        params.append(
            exclude_booking_id
        )

    cursor.execute(
        query,
        tuple(params)
    )

    direct_reserved = int(
        cursor.fetchone()[0] or 0
    )

    # =====================================================
    # PACKAGE BOOKINGS
    # =====================================================

    query = """
        SELECT
            COALESCE(SUM(bi.quantity), 0)

        FROM booking_items bi

        JOIN bookings b
            ON b.id = bi.booking_id

        WHERE bi.equipment_id = %s

          AND b.package_id IS NOT NULL

          AND b.payment_status = 'Paid'

          AND b.booking_status IN (
              'Confirmed',
              'Out for Delivery',
              'Delivered'
          )

          AND b.start_date < %s
          AND b.end_date > %s
    """

    params = [
        equipment_id,
        end_date,
        start_date
    ]

    if exclude_booking_id is not None:

        query += """
            AND b.id != %s
        """

        params.append(
            exclude_booking_id
        )

    cursor.execute(
        query,
        tuple(params)
    )

    package_reserved = int(
        cursor.fetchone()[0] or 0
    )

    return max(
        total_quantity
        - direct_reserved
        - package_reserved,
        0
    )    

def get_cart_physical_requirements(
    cursor,
    exclude_key=None
):
    """
    Return physical equipment reserved by the current cart.

    exclude_key excludes one cart line when calculating the
    maximum quantity for that line.
    """

    cart = get_cart()

    requirements = {}

    if not cart["items"]:
        return requirements


    for cart_item in cart["items"]:

        # ---------------------------------------------
        # Ignore the item whose quantity we are checking
        # ---------------------------------------------

        if (
            exclude_key
            and cart_item.get("key") == exclude_key
        ):
            continue


        item_type = cart_item.get("item_type")

        item_id = int(
            cart_item.get("item_id")
        )

        quantity = int(
            cart_item.get("quantity", 0)
        )


        if quantity <= 0:
            continue


        # ---------------------------------------------
        # DIRECT EQUIPMENT
        # ---------------------------------------------

        if item_type == "Equipment":

            requirements[item_id] = (
                requirements.get(item_id, 0)
                + quantity
            )


        # ---------------------------------------------
        # PACKAGE COMPONENTS
        # ---------------------------------------------

        elif item_type == "Package":

            package_data = get_package_availability(
                cursor,
                item_id,
                cart["start_date"],
                cart["end_date"]
            )

            if not package_data:
                continue


            for component in package_data["items"]:

                equipment_id = int(
                    component[0]
                )

                component_quantity = (
                    int(component[1])
                    * quantity
                )


                requirements[equipment_id] = (
                    requirements.get(
                        equipment_id,
                        0
                    )
                    + component_quantity
                )


    return requirements


def get_max_cart_quantity(
    cursor,
    item_type,
    item_id,
    start_date,
    end_date
):
    """
    Return the maximum TOTAL quantity allowed for
    one equipment/package cart line.
    """

    key = cart_item_key(
        item_type,
        item_id
    )


    # Physical inventory required by OTHER
    # cart items.
    other_requirements = (
        get_cart_physical_requirements(
            cursor,
            exclude_key=key
        )
    )


    # =================================================
    # EQUIPMENT
    # =================================================

    if item_type == "Equipment":

        cursor.execute("""
            SELECT
                total_quantity
            FROM equipment
            WHERE id = %s
              AND is_active = TRUE
        """, (
            item_id,
        ))

        equipment = cursor.fetchone()


        if not equipment:
            return 0


        database_available = (
            get_equipment_available_quantity(
                cursor,
                item_id,
                start_date,
                end_date
            )
        )


        other_reserved = int(
            other_requirements.get(
                int(item_id),
                0
            )
        )


        return min(
            max(
                database_available
                - other_reserved,
                0
            ),
            100
        )


    # =================================================
    # PACKAGE
    # =================================================

    if item_type == "Package":

        package_data = (
            get_package_availability(
                cursor,
                item_id,
                start_date,
                end_date
            )
        )


        if not package_data:
            return 0


        max_packages = int(
            package_data[
                "available_packages"
            ]
        )


        for component in package_data["items"]:

            equipment_id = int(
                component[0]
            )

            required_quantity = int(
                component[1]
            )


            database_available = (
                get_equipment_available_quantity(
                    cursor,
                    equipment_id,
                    start_date,
                    end_date
                )
            )


            other_reserved = int(
                other_requirements.get(
                    equipment_id,
                    0
                )
            )


            available_units = max(
                database_available
                - other_reserved,
                0
            )


            if required_quantity <= 0:
                max_packages = 0
                break


            component_capacity = (
                available_units
                // required_quantity
            )


            max_packages = min(
                max_packages,
                component_capacity
            )


        return min(
            max(max_packages, 0),
            100
        )


    return 0


def get_package_availability(
    cursor,
    package_id,
    start_date,
    end_date,
    exclude_booking_id=None
):
    """
    Returns:
        {
            "package": package row,
            "items": package component rows,
            "available_packages": int
        }

    Package is available only when every component has
    enough stock for the requested dates.
    """

    cursor.execute("""
        SELECT
            p.id,
            p.business_id,
            p.name,
            p.description,
            p.image,
            p.price_per_day,
            p.is_active,
            b.business_name,
            b.city
        FROM packages p
        JOIN businesses b
            ON b.id = p.business_id
        WHERE p.id = %s
          AND p.is_active = TRUE
          AND b.approval_status = 'Approved'
    """, (
        package_id,
    ))

    package = cursor.fetchone()

    if not package:
        return None

    cursor.execute("""
        SELECT
            pi.equipment_id,
            pi.quantity,
            e.name,
            e.category,
            e.description,
            e.price_per_day,
            e.image,
            e.total_quantity,
            e.available_quantity,
            e.is_active
        FROM package_items pi
        JOIN equipment e
            ON e.id = pi.equipment_id
        WHERE pi.package_id = %s
        ORDER BY pi.id
    """, (
        package_id,
    ))

    items = cursor.fetchall()

    if not items:
        return None

    max_package_quantity = None

    for item in items:

        equipment_id = item[0]
        required_quantity = int(item[1])
        total_quantity = int(item[7])
        is_active = bool(item[9])

        # Archived equipment makes the package unavailable
        if not is_active:
            return {
                "package": package,
                "items": items,
                "available_packages": 0
            }

        query = """
            SELECT
                COALESCE(
                    SUM(
                        CASE
                            WHEN b.equipment_id = %s
                            THEN b.quantity
                            ELSE 0
                        END
                    ),
                    0
                )
            FROM bookings b
            WHERE b.payment_status = 'Paid'
              AND b.booking_status IN (
                    'Confirmed',
                    'Out for Delivery',
                    'Delivered'
              )
              AND b.start_date < %s
              AND b.end_date > %s
        """

        params = [
            equipment_id,
            end_date,
            start_date
        ]

        if exclude_booking_id is not None:
            query += " AND b.id != %s"
            params.append(exclude_booking_id)

        cursor.execute(
            query,
            tuple(params)
        )

        direct_reserved = int(
            cursor.fetchone()[0] or 0
        )

        # Package bookings reserve their individual components
        query = """
            SELECT
                COALESCE(SUM(bi.quantity), 0)
            FROM booking_items bi
            JOIN bookings b
                ON b.id = bi.booking_id
            WHERE bi.equipment_id = %s
              AND b.package_id IS NOT NULL
              AND b.payment_status = 'Paid'
              AND b.booking_status IN (
                    'Confirmed',
                    'Out for Delivery',
                    'Delivered'
              )
              AND b.start_date < %s
              AND b.end_date > %s
        """

        params = [
            equipment_id,
            end_date,
            start_date
        ]

        if exclude_booking_id is not None:
            query += " AND b.id != %s"
            params.append(exclude_booking_id)

        cursor.execute(
            query,
            tuple(params)
        )

        package_reserved = int(
            cursor.fetchone()[0] or 0
        )

        reserved = (
            direct_reserved +
            package_reserved
        )

        available_units = max(
            total_quantity - reserved,
            0
        )

        component_package_capacity = (
            available_units // required_quantity
        )

        if max_package_quantity is None:

            max_package_quantity = (
                component_package_capacity
            )

        else:

            max_package_quantity = min(
                max_package_quantity,
                component_package_capacity
            )

    return {
        "package": package,
        "items": items,
        "available_packages": max(
            max_package_quantity or 0,
            0
        )
    }


def validate_combined_inventory(
    cursor,
    items,
    start_date,
    end_date
):
    """
    Validate the combined physical equipment requirements
    of an entire cart/order.

    Direct equipment and package components are aggregated
    together so the same physical equipment cannot be
    oversold through multiple cart items.
    """

    required_inventory = {}

    # -------------------------------------------------
    # BUILD TOTAL PHYSICAL REQUIREMENTS
    # -------------------------------------------------

    for item in items:

        item_type = item["type"]
        item_id = int(item["id"])
        item_quantity = int(item["quantity"])

        if item_type == "Equipment":

            equipment_id = item_id

            required_inventory[equipment_id] = (
                required_inventory.get(equipment_id, 0)
                + item_quantity
            )

        elif item_type == "Package":

            package_data = get_package_availability(
                cursor,
                item_id,
                start_date,
                end_date
            )

            if not package_data:

                return {
                    "success": False,
                    "message": (
                        "A package in this order "
                        "is no longer available."
                    )
                }

            for component in package_data["items"]:

                equipment_id = int(component[0])

                component_quantity = (
                    int(component[1])
                    * item_quantity
                )

                required_inventory[equipment_id] = (
                    required_inventory.get(equipment_id, 0)
                    + component_quantity
                )

        else:

            return {
                "success": False,
                "message": "Invalid order item."
            }

    # -------------------------------------------------
    # LOCK ALL INVOLVED EQUIPMENT ROWS
    # -------------------------------------------------

    equipment_ids = sorted(
        required_inventory.keys()
    )

    for equipment_id in equipment_ids:

        cursor.execute("""
            SELECT
                id,
                name,
                total_quantity,
                is_active
            FROM equipment
            WHERE id = %s
            FOR UPDATE
        """, (
            equipment_id,
        ))

        equipment = cursor.fetchone()

        if not equipment:

            return {
                "success": False,
                "message": (
                    "One of the required equipment "
                    "items no longer exists."
                )
            }

        if not equipment[3]:

            return {
                "success": False,
                "message": (
                    f'"{equipment[1]}" is no longer available.'
                )
            }

    # -------------------------------------------------
    # CHECK COMBINED DATE-SPECIFIC AVAILABILITY
    # -------------------------------------------------

    for equipment_id in equipment_ids:

        required_quantity = int(
            required_inventory[equipment_id]
        )

        available_quantity = (
            get_equipment_available_quantity(
                cursor,
                equipment_id,
                start_date,
                end_date
            )
        )

        if required_quantity > available_quantity:

            cursor.execute("""
                SELECT name
                FROM equipment
                WHERE id = %s
            """, (
                equipment_id,
            ))

            row = cursor.fetchone()

            equipment_name = (
                row[0]
                if row
                else "Equipment"
            )

            return {
                "success": False,
                "message": (
                    f'"{equipment_name}" does not have enough '
                    f'stock for this order. '
                    f'Required: {required_quantity}, '
                    f'available: {available_quantity}.'
                )
            }

    return {
        "success": True,
        "requirements": required_inventory
    }

def get_future_committed_peak_quantity(
    cursor,
    equipment_id
):
    """
    Returns the maximum number of units of an equipment item
    committed simultaneously in future paid bookings.

    Package components are included because booking_items
    contains the physical inventory snapshot.
    """

    tomorrow = datetime.now().date() + timedelta(days=1)

    cursor.execute("""
        SELECT
            b.start_date,
            b.end_date,
            bi.quantity
        FROM booking_items bi
        JOIN bookings b
            ON bi.booking_id = b.id
        WHERE bi.equipment_id = %s
          AND b.payment_status = 'Paid'
          AND b.booking_status IN (
              'Confirmed',
              'Out for Delivery',
              'Delivered'
          )
          AND b.end_date > %s
        ORDER BY
            b.start_date ASC,
            b.end_date ASC
    """, (
        equipment_id,
        tomorrow
    ))

    rows = cursor.fetchall()

    events = []

    for start_date, end_date, quantity in rows:

        quantity = int(quantity)

        events.append(
            (
                start_date,
                1,
                quantity
            )
        )

        events.append(
            (
                end_date,
                -1,
                quantity
            )
        )

    # End events must be processed before start events
    # on the same date.
    events.sort(
        key=lambda event: (
            event[0],
            event[1]
        )
    )

    current = 0
    peak = 0

    for _, event_type, quantity in events:

        current += (
            quantity
            if event_type == 1
            else -quantity
        )

        peak = max(
            peak,
            current
        )

    return peak

# =========================================================
# CUSTOMER PACKAGES
# =========================================================

@app.route("/packages")
def packages():

    if not customer_logged_in():
        return redirect(url_for("login"))

    cursor = mysql.connection.cursor()

    try:

        cursor.execute("""
            SELECT
                p.id,
                p.name,
                p.description,
                p.image,
                p.price_per_day,
                b.business_name,
                b.city,
                COUNT(pi.id)
            FROM packages p
            JOIN businesses b
                ON b.id = p.business_id
            LEFT JOIN package_items pi
                ON pi.package_id = p.id
            WHERE p.is_active = TRUE
              AND b.approval_status = 'Approved'
              AND NOT EXISTS (
                    SELECT 1
                    FROM package_items pi2
                    JOIN equipment e2
                        ON e2.id = pi2.equipment_id
                    WHERE pi2.package_id = p.id
                      AND e2.is_active = FALSE
              )
            GROUP BY
                p.id,
                p.name,
                p.description,
                p.image,
                p.price_per_day,
                b.business_name,
                b.city
            ORDER BY p.created_at DESC
        """)

        package_list = cursor.fetchall()

        return render_template(
            "packages.html",
            package_list=package_list,
            user_name=session["user_name"]
        )

    finally:
        cursor.close()


@app.route("/packages/<int:package_id>")
def package_details(package_id):

    if not customer_logged_in():
        return redirect(url_for("login"))

    cursor = mysql.connection.cursor()

    try:

        package_data = get_package_availability(
            cursor,
            package_id,
            datetime.now().date(),
            datetime.now().date() + timedelta(days=1)
        )

        if not package_data:
            return "Package not found.", 404

        return render_template(
            "package_details.html",
            package=package_data["package"],
            package_items=package_data["items"],
            available_packages=package_data["available_packages"],
            user_name=session["user_name"]
        )

    finally:
        cursor.close()
        
@app.route(
    "/rent-package/<int:package_id>"
)
def rent_package(package_id):

    if not customer_logged_in():

        return redirect(
            url_for("login")
        )


    cursor = mysql.connection.cursor()


    try:

        cart = get_cart()


        package_data = (
            get_package_availability(
                cursor,
                package_id,
                datetime.now().date(),
                datetime.now().date()
                + timedelta(days=1)
            )
        )


        if not package_data:

            return (
                "Package not found.",
                404
            )


        key = cart_item_key(
            "Package",
            package_id
        )


        existing = next(
            (
                cart_item
                for cart_item in cart["items"]
                if cart_item.get("key") == key
            ),
            None
        )


        current_quantity = int(

            existing.get(
                "quantity",
                0
            )

            if existing

            else 0

        )


        return render_template(

            "rent_package.html",

            package=
                package_data["package"],

            package_items=
                package_data["items"],

            available_packages=
                package_data[
                    "available_packages"
                ],

            current_quantity=
                current_quantity,

            cart_start_date=
                cart.get(
                    "start_date"
                ),

            cart_end_date=
                cart.get(
                    "end_date"
                ),

            cart_has_items=
                bool(cart["items"]),

            user_name=
                session["user_name"]

        )


    finally:

        cursor.close()


@app.route(
    "/check-package-availability/<int:package_id>"
)
def check_package_availability(package_id):

    if not customer_logged_in():

        return jsonify({
            "success": False,
            "message": "Please login as a customer."
        }), 401


    start_date = request.args.get(
        "start_date",
        ""
    ).strip()

    end_date = request.args.get(
        "end_date",
        ""
    ).strip()


    if not start_date or not end_date:

        return jsonify({
            "success": False,
            "message": "Please select both dates."
        }), 400


    try:

        start = datetime.strptime(
            start_date,
            "%Y-%m-%d"
        ).date()

        end = datetime.strptime(
            end_date,
            "%Y-%m-%d"
        ).date()

    except ValueError:

        return jsonify({
            "success": False,
            "message": "Invalid date."
        }), 400


    total_days = (
        end - start
    ).days


    if total_days <= 0:

        return jsonify({
            "success": False,
            "message": (
                "End date must be after "
                "the start date."
            )
        }), 400


    if total_days > 30:

        return jsonify({
            "success": False,
            "message": (
                "Rental period cannot "
                "exceed 30 days."
            )
        }), 400


    cursor = mysql.connection.cursor()


    try:

        package_data = (
            get_package_availability(
                cursor,
                package_id,
                start,
                end
            )
        )


        if not package_data:

            return jsonify({
                "success": False,
                "message": "Package not found."
            }), 404


        max_packages = (
            get_max_cart_quantity(
                cursor,
                "Package",
                package_id,
                start,
                end
            )
        )


        return jsonify({

            "success": True,

            "available_packages":
                max_packages,

            "max_quantity":
                max_packages

        })


    finally:

        cursor.close()
    

@app.route('/business-dashboard')
def business_dashboard():

    if (
        "user_id" not in session
        or session.get("user_type") != "Business"
        or "business_id" not in session
    ):
        return redirect(url_for("business_login"))

    business_id = session["business_id"]
    cursor = mysql.connection.cursor()

    try:

        # =====================================================
        # BUSINESS
        # =====================================================

        cursor.execute("""
            SELECT
                id,
                business_name,
                city,
                approval_status
            FROM businesses
            WHERE id = %s
        """, (business_id,))

        business = cursor.fetchone()

        if not business:
            session.pop("business_id", None)
            return redirect(url_for("business_login"))

        if business[3] != "Approved":
            return redirect(url_for("business_login"))

        today = datetime.now().date()

        # =====================================================
        # EQUIPMENT
        # =====================================================

        cursor.execute("""
            SELECT
                id,
                name,
                category,
                description,
                price_per_day,
                image,
                available,
                total_quantity,
                available_quantity,
                is_active
            FROM equipment
            WHERE business_id = %s
            ORDER BY created_at DESC
        """, (business_id,))

        equipment = cursor.fetchall()

        total_equipment = len(equipment)

        available_equipment = sum(
            1
            for item in equipment
            if item[6] == 1 and item[9] == 1
        )

        # =====================================================
        # TOTAL ACTIVE BOOKINGS
        # =====================================================

        cursor.execute("""
            SELECT COUNT(*)
            FROM bookings b
            LEFT JOIN equipment e
                ON b.equipment_id = e.id

            LEFT JOIN packages pkg
                ON b.package_id = pkg.id
            WHERE (
                e.business_id = %s
                OR pkg.business_id = %s
            )
              AND b.booking_status NOT IN (
                  'Cancelled',
                  'Completed'
              )
        """, (business_id,
              business_id,))

        total_bookings = cursor.fetchone()[0]

        # =====================================================
        # UPCOMING DELIVERIES
        # Confirmed bookings with delivery date today/future
        # =====================================================

        cursor.execute("""
            SELECT COUNT(*)
            FROM bookings b
            LEFT JOIN equipment e
                ON b.equipment_id = e.id

            LEFT JOIN packages pkg
                ON b.package_id = pkg.id
            WHERE (
                e.business_id = %s
                OR pkg.business_id = %s
            )
              AND b.booking_status = 'Confirmed'
              AND b.payment_status = 'Paid'
              AND b.start_date >= %s
        """, (business_id,business_id, today))

        upcoming_deliveries = cursor.fetchone()[0]

        # =====================================================
        # OUT FOR DELIVERY
        # =====================================================

        cursor.execute("""
            SELECT COUNT(*)
            FROM bookings b
            LEFT JOIN equipment e
                ON b.equipment_id = e.id

            LEFT JOIN packages pkg
                ON b.package_id = pkg.id
            WHERE (
                e.business_id = %s
                OR pkg.business_id = %s
            )
              AND b.booking_status = 'Out for Delivery'
              AND b.payment_status = 'Paid'
        """, (business_id,business_id,))

        out_for_delivery = cursor.fetchone()[0]

        # =====================================================
        # ACTIVE RENTALS
        # Delivered = currently with customer
        # =====================================================

        cursor.execute("""
            SELECT COUNT(*)
            FROM bookings b
            LEFT JOIN equipment e
                ON b.equipment_id = e.id

            LEFT JOIN packages pkg
                ON b.package_id = pkg.id
            WHERE (
                e.business_id = %s
                OR pkg.business_id = %s
            )
              AND b.booking_status = 'Delivered'
              AND b.payment_status = 'Paid'
        """, (business_id,business_id,))

        active_rentals = cursor.fetchone()[0]

        # =====================================================
        # RETURNS DUE TODAY
        # =====================================================

        cursor.execute("""
            SELECT COUNT(*)
            FROM bookings b
            LEFT JOIN equipment e
                ON b.equipment_id = e.id

            LEFT JOIN packages pkg
                ON b.package_id = pkg.id
            WHERE (
                e.business_id = %s
                OR pkg.business_id = %s
            )
              AND b.booking_status = 'Delivered'
              AND b.payment_status = 'Paid'
              AND b.end_date = %s
        """, (business_id,business_id, today))

        returns_due_today = cursor.fetchone()[0]

        # =====================================================
        # OVERDUE RETURNS
        # =====================================================

        cursor.execute("""
            SELECT COUNT(*)
            FROM bookings b
            LEFT JOIN equipment e
                ON b.equipment_id = e.id

            LEFT JOIN packages pkg
                ON b.package_id = pkg.id
            WHERE (
                e.business_id = %s
                OR pkg.business_id = %s
            )
              AND b.booking_status = 'Delivered'
              AND b.payment_status = 'Paid'
              AND b.end_date < %s
        """, (business_id,business_id, today))

        overdue_returns = cursor.fetchone()[0]

        # =====================================================
        # UPCOMING DELIVERY LIST
        # =====================================================

        cursor.execute("""
            SELECT
                b.id,
                b.start_date,
                b.end_date,
                b.quantity,

                COALESCE(
                    e.name,
                    pkg.name
                ) AS item_name,

                u.full_name

            FROM bookings b

            LEFT JOIN equipment e
                ON b.equipment_id = e.id

            LEFT JOIN packages pkg
                ON b.package_id = pkg.id

            JOIN users u
                ON b.user_id = u.id

            WHERE (
                e.business_id = %s
                OR pkg.business_id = %s
            )

            AND b.booking_status = 'Confirmed'
            AND b.payment_status = 'Paid'
            AND b.start_date >= %s

            ORDER BY
                b.start_date ASC,
                b.id ASC

            LIMIT 5
        """, (
            business_id,
            business_id,
            today
        ))

        upcoming_delivery_list = cursor.fetchall()

        # =====================================================
        # PAYOUTS
        # =====================================================

        cursor.execute("""
            SELECT

                COALESCE(
                    SUM(
                        CASE
                            WHEN p.payout_status = 'Held'
                            AND b.payment_status = 'Paid'
                            AND b.booking_status IN (
                                'Confirmed',
                                'Out for Delivery',
                                'Delivered'
                            )
                            THEN p.amount
                            ELSE 0
                        END
                    ),
                    0
                ),

                COALESCE(
                    SUM(
                        CASE
                            WHEN p.payout_status = 'Released'
                            THEN p.amount
                            ELSE 0
                        END
                    ),
                    0
                ),

                COALESCE(
                    SUM(
                        CASE
                            WHEN p.payout_status != 'Cancelled'
                            THEN p.amount
                            ELSE 0
                        END
                    ),
                    0
                )

            FROM payouts p

            JOIN bookings b
                ON p.booking_id = b.id

            WHERE p.business_id = %s
        """, (
            business_id,
        ))

        payout_stats = cursor.fetchone()

        held_payouts = payout_stats[0]
        released_payouts = payout_stats[1]
        total_earnings = payout_stats[2]

        return render_template(
            "business_dashboard.html",
            business=business,
            equipment=equipment,

            total_equipment=total_equipment,
            available_equipment=available_equipment,

            total_bookings=total_bookings,

            upcoming_deliveries=upcoming_deliveries,
            out_for_delivery=out_for_delivery,
            active_rentals=active_rentals,
            returns_due_today=returns_due_today,
            overdue_returns=overdue_returns,

            upcoming_delivery_list=upcoming_delivery_list,

            total_earnings=total_earnings,
            held_payouts=held_payouts,
            released_payouts=released_payouts
        )

    finally:
        cursor.close()


# =========================================================
# BUSINESS EQUIPMENT MANAGEMENT PAGE
# =========================================================

@app.route("/business/equipment")
def business_equipment():

    if (
        "user_id" not in session
        or session.get("user_type") != "Business"
        or "business_id" not in session
    ):
        return redirect(url_for("business_login"))

    business_id = session["business_id"]

    cursor = mysql.connection.cursor()

    try:

        # -------------------------------------------------
        # BUSINESS
        # -------------------------------------------------

        cursor.execute("""
            SELECT
                id,
                business_name,
                city,
                approval_status
            FROM businesses
            WHERE id = %s
              AND user_id = %s
        """, (
            business_id,
            session["user_id"]
        ))

        business = cursor.fetchone()

        if not business:
            return redirect(url_for("business_login"))

        if business[3] != "Approved":
            return redirect(url_for("business_login"))


        # -------------------------------------------------
        # BUSINESS EQUIPMENT
        # -------------------------------------------------

        cursor.execute("""
            SELECT
                id,
                name,
                category,
                description,
                price_per_day,
                image,
                available,
                total_quantity,
                available_quantity,
                is_active
            FROM equipment
            WHERE business_id = %s
            ORDER BY created_at DESC
        """, (
            business_id,
        ))

        equipment = cursor.fetchall()


        return render_template(
            "business_equipment.html",
            business=business,
            equipment=equipment
        )

    finally:

        cursor.close()

    
@app.route('/business-bookings')
def business_bookings():

    if (
        "user_id" not in session
        or session.get("user_type") != "Business"
        or "business_id" not in session
    ):
        return redirect(url_for("business_login"))

    business_id = session["business_id"]

    cursor = mysql.connection.cursor()

    try:
        # =====================================================
        # LOAD BUSINESS
        # =====================================================

        cursor.execute("""
            SELECT
                id,
                business_name,
                city,
                approval_status
            FROM businesses
            WHERE id = %s
        """, (
            business_id,
        ))

        business = cursor.fetchone()

        if not business:
            session.pop("business_id", None)

            return redirect(
                url_for("business_login")
            )

        if business[3] != "Approved":
            return redirect(
                url_for("business_status")
            )
            
            
        cursor.execute("""
            SELECT
                b.id,
                b.order_id,
                b.quantity,
                b.start_date,
                b.end_date,
                b.total_days,
                b.daily_rate,
                b.total_amount,
                b.booking_status,
                b.payment_status,

                b.equipment_id,
                b.package_id,

                COALESCE(
                    e.name,
                    pkg.name
                ) AS item_name,

                CASE
                    WHEN b.package_id IS NOT NULL
                    THEN 'Rental Package'
                    ELSE e.category
                END AS category,

                u.full_name,

                o.total_amount AS order_total,
                o.order_status,
                o.payment_status AS order_payment_status

            FROM bookings b

            LEFT JOIN equipment e
                ON b.equipment_id = e.id

            LEFT JOIN packages pkg
                ON b.package_id = pkg.id

            JOIN users u
                ON b.user_id = u.id

            LEFT JOIN orders o
                ON b.order_id = o.id

            WHERE (
                e.business_id = %s
                OR pkg.business_id = %s
            )

            ORDER BY
                COALESCE(
                    b.order_id,
                    b.id
                ) DESC,

                b.id DESC
        """, (
            business_id,
            business_id
        ))

        rows = cursor.fetchall()

        grouped = {}

        for row in rows:

            order_id = row[1]

            key = (
                f"order-{order_id}"
                if order_id is not None
                else f"booking-{row[0]}"
            )

            if key not in grouped:

                grouped[key] = {

                    "is_order":
                        order_id is not None,

                    "order_id":
                        order_id,

                    "display_id":
                        (
                            order_id
                            if order_id is not None
                            else row[0]
                        ),

                    "customer":
                        row[14],

                    "start_date":
                        row[3],

                    "end_date":
                        row[4],

                    "total_days":
                        row[5],

                    "order_total":
                        (
                            float(row[15])
                            if (
                                order_id is not None
                                and row[15] is not None
                            )
                            else None
                        ),

                    "order_status":
                        row[16],

                    "order_payment_status":
                        row[17],

                    "items": []
                }


            grouped[key]["items"].append({

                "booking_id":
                    row[0],

                "quantity":
                    row[2],

                "start_date":
                    row[3],

                "end_date":
                    row[4],

                "total_days":
                    row[5],

                "daily_rate":
                    float(row[6]),

                "total_amount":
                    float(row[7]),

                "booking_status":
                    row[8],

                "payment_status":
                    row[9],

                "item_name":
                    row[12],

                "category":
                    row[13]

            })


        booking_groups = list(
            grouped.values()
        )

        for group in booking_groups:

            statuses = {
                item["booking_status"]
                for item in group["items"]
            }

            group["status"] = (
                next(iter(statuses))
                if len(statuses) == 1
                else "Multiple statuses"
            )

        return render_template(
            "business_bookings.html",
            business=business,
            booking_groups=booking_groups,
            today=datetime.now().date()
        )

    finally:
        cursor.close()
        
    
@app.route(
    '/business-booking/<int:booking_id>/<status>',
    methods=['POST']
)
def update_booking_status(booking_id, status):

    if (
        "user_id" not in session
        or session.get("user_type") != "Business"
        or "business_id" not in session
    ):
        return redirect(url_for("business_login"))

    allowed_statuses = {
        "Out for Delivery",
        "Delivered",
        "Returned",
        "Completed"
    }

    if status not in allowed_statuses:
        return "Invalid booking status.", 400

    business_id = session["business_id"]

    cursor = mysql.connection.cursor()

    try:

        # =====================================================
        # GET BOOKING + VERIFY BUSINESS OWNERSHIP
        # Works for equipment AND package bookings
        # =====================================================

        cursor.execute("""
            SELECT
                b.id,
                b.quantity,
                b.start_date,
                b.end_date,
                b.booking_status,
                b.payment_status,
                b.equipment_id,
                b.package_id,
                b.user_id
            FROM bookings b
            LEFT JOIN equipment e
                ON b.equipment_id = e.id
            LEFT JOIN packages p
                ON b.package_id = p.id
            WHERE b.id = %s
              AND (
                    e.business_id = %s
                    OR p.business_id = %s
              )
            FOR UPDATE
        """, (
            booking_id,
            business_id,
            business_id
        ))

        booking = cursor.fetchone()

        if not booking:
            return "Booking not found.", 404

        quantity = int(booking[1])
        start_date = booking[2]
        end_date = booking[3]
        current_status = booking[4]
        payment_status = booking[5]
        equipment_id = booking[6]
        package_id = booking[7]
        customer_user_id = booking[8]

        today = datetime.now().date()

        if payment_status != "Paid":
            return "This booking has not been paid.", 400

        # =====================================================
        # GET ACTUAL INVENTORY ITEMS
        # =====================================================

        if package_id:

            cursor.execute("""
                SELECT
                    bi.equipment_id,
                    bi.quantity,
                    e.name,
                    e.total_quantity,
                    e.available_quantity,
                    e.is_active
                FROM booking_items bi
                JOIN equipment e
                    ON bi.equipment_id = e.id
                WHERE bi.booking_id = %s
                  AND bi.source = 'Package'
                ORDER BY bi.equipment_id
                FOR UPDATE
            """, (
                booking_id,
            ))

            inventory_items = cursor.fetchall()

            if not inventory_items:
                return (
                    "Package booking components could not be found.",
                    400
                )

        else:

            cursor.execute("""
                SELECT
                    id,
                    %s,
                    name,
                    total_quantity,
                    available_quantity,
                    is_active
                FROM equipment
                WHERE id = %s
                FOR UPDATE
            """, (
                quantity,
                equipment_id
            ))

            equipment = cursor.fetchone()

            if not equipment:
                return "Equipment not found.", 404

            inventory_items = [equipment]

        # =====================================================
        # CONFIRMED → OUT FOR DELIVERY
        # =====================================================

        if status == "Out for Delivery":

            if current_status != "Confirmed":
                return (
                    "This booking is not ready for delivery.",
                    400
                )

            if today < start_date:
                return (
                    "Equipment cannot be sent out before "
                    "the delivery date.",
                    400
                )

            # Check ALL physical components before changing ANY
            for item in inventory_items:

                item_equipment_id = item[0]
                required_quantity = int(item[1])
                item_name = item[2]
                available_quantity = int(item[4] or 0)

                if available_quantity < required_quantity:
                    mysql.connection.rollback()

                    return (
                        f'The equipment "{item_name}" is not '
                        f'physically available in the required '
                        f'quantity.',
                        400
                    )

            # Decrement ALL components atomically
            for item in inventory_items:

                item_equipment_id = item[0]
                required_quantity = int(item[1])

                cursor.execute("""
                    UPDATE equipment
                    SET
                        available_quantity =
                            available_quantity - %s,
                        available = CASE
                            WHEN available_quantity - %s > 0
                            THEN 1
                            ELSE 0
                        END
                    WHERE id = %s
                      AND is_active = TRUE
                      AND available_quantity >= %s
                """, (
                    required_quantity,
                    required_quantity,
                    item_equipment_id,
                    required_quantity
                ))

                if cursor.rowcount != 1:

                    mysql.connection.rollback()

                    return (
                        "Inventory changed while processing "
                        "this booking. Please try again.",
                        400
                    )

            cursor.execute("""
                UPDATE bookings
                SET booking_status = 'Out for Delivery'
                WHERE id = %s
                  AND booking_status = 'Confirmed'
            """, (
                booking_id,
            ))

            if cursor.rowcount != 1:
                mysql.connection.rollback()
                return (
                    "The booking status could not be updated.",
                    400
                )

            # =================================================
            # AUTOMATIC BUSINESS FUND RELEASE
            # =================================================

            cursor.execute("""
                UPDATE payouts
                SET
                    payout_status = 'Released',
                    payout_reference = 'INTERNAL-AUTO-RELEASE',
                    paid_at = NOW()
                WHERE booking_id = %s
                  AND payout_status = 'Held'
            """, (
                booking_id,
            ))

            cursor.execute("""
                SELECT
                    p.amount,
                    b.user_id
                FROM payouts p
                JOIN businesses b
                    ON p.business_id = b.id
                WHERE p.booking_id = %s
                  AND p.payout_status = 'Released'
                LIMIT 1
            """, (
                booking_id,
            ))

            released_payout = cursor.fetchone()

            if released_payout:

                create_notification(
                    released_payout[1],
                    "payout_released",
                    "Payment Credited",
                    (
                        f"₹{float(released_payout[0]):.2f} from "
                        f"booking #{booking_id} has been released "
                        f"to your business account."
                    ),
                    url_for("business_dashboard")
                )

        # =====================================================
        # OUT FOR DELIVERY → DELIVERED
        # =====================================================

        elif status == "Delivered":

            if current_status != "Out for Delivery":
                return (
                    "This booking cannot be marked as delivered.",
                    400
                )

            if today < start_date:
                return (
                    "This equipment cannot be marked as delivered "
                    "before the delivery date.",
                    400
                )

            cursor.execute("""
                UPDATE bookings
                SET booking_status = 'Delivered'
                WHERE id = %s
                  AND booking_status = 'Out for Delivery'
            """, (
                booking_id,
            ))

        # =====================================================
        # DELIVERED → RETURNED
        # =====================================================

        elif status == "Returned":

            if current_status != "Delivered":
                return (
                    "This booking cannot be marked as returned.",
                    400
                )

            if today < end_date:
                return (
                    "This equipment cannot be marked as returned "
                    "before the rental end date.",
                    400
                )

            cursor.execute("""
                UPDATE bookings
                SET booking_status = 'Returned'
                WHERE id = %s
                  AND booking_status = 'Delivered'
            """, (
                booking_id,
            ))

            if cursor.rowcount != 1:
                return (
                    "The booking status could not be updated.",
                    400
                )

            # Restore ALL physical components
            for item in inventory_items:

                item_equipment_id = item[0]
                returned_quantity = int(item[1])

                cursor.execute("""
                    UPDATE equipment
                    SET
                        available_quantity = LEAST(
                            available_quantity + %s,
                            total_quantity
                        ),
                        available = 1
                    WHERE id = %s
                """, (
                    returned_quantity,
                    item_equipment_id
                ))

        # =====================================================
        # RETURNED → COMPLETED
        # =====================================================

        elif status == "Completed":

            if current_status != "Returned":
                return (
                    "This booking must be marked as returned "
                    "before it can be completed.",
                    400
                )

            cursor.execute("""
                UPDATE bookings
                SET booking_status = 'Completed'
                WHERE id = %s
                  AND booking_status = 'Returned'
            """, (
                booking_id,
            ))

        # =====================================================
        # CUSTOMER NOTIFICATIONS
        # =====================================================

        if status == "Out for Delivery":

            create_notification(
                customer_user_id,
                "delivery_started",
                "Out for Delivery",
                (
                    f"Your booking #{booking_id} "
                    f"is now out for delivery."
                ),
                url_for("my_rentals")
            )

        elif status == "Delivered":

            create_notification(
                customer_user_id,
                "rental_active",
                "Rental Delivered",
                (
                    f"Your booking #{booking_id} has been "
                    f"delivered and your rental is now active."
                ),
                url_for("my_rentals")
            )

        elif status == "Returned":

            create_notification(
                customer_user_id,
                "equipment_returned",
                "Equipment Returned",
                (
                    f"The equipment for booking #{booking_id} "
                    f"has been marked as returned."
                ),
                url_for("my_rentals")
            )

        elif status == "Completed":

            create_notification(
                customer_user_id,
                "booking_completed",
                "Rental Completed",
                (
                    f"Your booking #{booking_id} "
                    f"has been completed successfully."
                ),
                url_for("my_rentals")
            )

        mysql.connection.commit()

        return redirect(
            url_for("business_bookings")
        )

    except Exception as e:

        mysql.connection.rollback()

        print(
            "Booking status update failed:",
            e
        )

        return (
            "Unable to update booking status.",
            500
        )

    finally:
        cursor.close()
    
@app.route('/business/edit-equipment/<int:equipment_id>', methods=['GET', 'POST'])
def edit_equipment(equipment_id):

    # Business must be logged in
    if (
        "user_id" not in session
        or session.get("user_type") != "Business"
        or "business_id" not in session
    ):
        return redirect(url_for("business_login"))

    business_id = session["business_id"]

    cursor = mysql.connection.cursor()

    try:

        # =========================
        # GET EQUIPMENT
        # =========================

        cursor.execute("""
            SELECT
                id,
                name,
                category,
                description,
                price_per_day,
                image,
                total_quantity,
                available_quantity
            FROM equipment
            WHERE id = %s
              AND business_id = %s
        """, (
            equipment_id,
            business_id
        ))

        equipment = cursor.fetchone()

        if not equipment:
            cursor.close()
            return "Equipment not found.", 404

        # =========================
        # SHOW EDIT FORM
        # =========================

        if request.method == "GET":

            cursor.close()

            return render_template(
                "business_edit_equipment.html",
                equipment=equipment
            )

        # =========================
        # GET FORM DATA
        # =========================

        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        price_per_day = request.form.get("price_per_day", "").strip()
        total_quantity = request.form.get("total_quantity", "").strip()

        image = request.files.get("image")

        # =========================
        # BASIC VALIDATION
        # =========================

        if not name or not category or not price_per_day or not total_quantity:

            return render_template(
                "business_edit_equipment.html",
                equipment=equipment,
                error="Please complete all required fields."
            )

        # =========================
        # VALIDATE PRICE
        # =========================

        try:
            price_per_day = float(price_per_day)

        except ValueError:

            return render_template(
                "business_edit_equipment.html",
                equipment=equipment,
                error="Please enter a valid rental price."
            )

        if price_per_day <= 0:

            return render_template(
                "business_edit_equipment.html",
                equipment=equipment,
                error="Rental price must be greater than zero."
            )

        # =========================
        # VALIDATE QUANTITY
        # =========================

        try:
            total_quantity = int(total_quantity)

        except ValueError:

            return render_template(
                "business_edit_equipment.html",
                equipment=equipment,
                error="Quantity must be a whole number."
            )

        if total_quantity < 1:

            return render_template(
                "business_edit_equipment.html",
                equipment=equipment,
                error="Quantity must be at least 1."
            )

        current_total = int(
            equipment[6]
        )

        current_available = int(
            equipment[7]
        )

        # Units physically out right now
        rented_quantity = (
            current_total
            - current_available
        )

        # Future confirmed/active reservations,
        # including package component reservations.
        future_committed_quantity = (
            get_future_committed_peak_quantity(
                cursor,
                equipment_id
            )
        )

        minimum_required_quantity = max(
            rented_quantity,
            future_committed_quantity
        )

        if total_quantity < minimum_required_quantity:

            return render_template(
                "business_edit_equipment.html",
                equipment=equipment,
                error=(
                    f"Your current/future bookings require at least "
                    f"{minimum_required_quantity} unit(s) of this "
                    f"equipment. Total quantity cannot be lower than that."
                )
            )

        # Available physical stock remains based on units
        # currently out with customers.
        new_available_quantity = (
            total_quantity
            - rented_quantity
        )

        new_available = (
            1
            if new_available_quantity > 0
            else 0
        )

        # =========================
        # CALCULATE NEW AVAILABLE STOCK
        # =========================

        new_available_quantity = total_quantity - rented_quantity

        new_available = 1 if new_available_quantity > 0 else 0

        # =========================
        # UPDATE WITHOUT NEW IMAGE
        # =========================

        if not image or not image.filename:

            cursor.execute("""
                UPDATE equipment
                SET
                    name = %s,
                    category = %s,
                    description = %s,
                    price_per_day = %s,
                    total_quantity = %s,
                    available_quantity = %s,
                    available = %s
                WHERE id = %s
                  AND business_id = %s
            """, (
                name,
                category,
                description,
                price_per_day,
                total_quantity,
                new_available_quantity,
                new_available,
                equipment_id,
                business_id
            ))

        # =========================
        # UPDATE WITH NEW IMAGE
        # =========================

        else:

            filename = secure_filename(
                image.filename
            )

            if not filename:

                return render_template(
                    "business_edit_equipment.html",
                    equipment=equipment,
                    error="Please select a valid image."
                )

            extension = get_file_extension(filename)

            if extension not in ALLOWED_EQUIPMENT_IMAGES:

                return render_template(
                    "business_edit_equipment.html",
                    equipment=equipment,
                    error=(
                        "Only JPG, JPEG, PNG and WEBP images are allowed."
                    )
                )

            # Check file size
            image.stream.seek(0, os.SEEK_END)
            image_size = image.stream.tell()
            image.stream.seek(0)

            if image_size > MAX_EQUIPMENT_IMAGE_SIZE:

                return render_template(
                    "business_edit_equipment.html",
                    equipment=equipment,
                    error="Equipment image must be 5 MB or smaller."
                )

            # Check actual file contents
            if not valid_file_signature(image, extension):

                return render_template(
                    "business_edit_equipment.html",
                    equipment=equipment,
                    error=(
                        "The uploaded file does not appear to be "
                        "a valid image."
                    )
                )

            unique_filename = (
                f"equipment_{business_id}_"
                f"{uuid.uuid4().hex}.{extension}"
            )

            image_path = os.path.join(
                EQUIPMENT_UPLOAD_FOLDER,
                unique_filename
            )

            image.save(image_path)

            cursor.execute("""
                UPDATE equipment
                SET
                    name = %s,
                    category = %s,
                    description = %s,
                    price_per_day = %s,
                    image = %s,
                    total_quantity = %s,
                    available_quantity = %s,
                    available = %s
                WHERE id = %s
                AND business_id = %s
            """, (
                name,
                category,
                description,
                price_per_day,
                unique_filename,
                total_quantity,
                new_available_quantity,
                new_available,
                equipment_id,
                business_id
            ))

        mysql.connection.commit()

        cursor.close()

        return redirect(
            url_for("business_dashboard")
        )

    except Exception as e:

        mysql.connection.rollback()
        cursor.close()

        print("Equipment update failed:", e)

        return "Unable to update equipment.", 500


def create_order_refund(
    cursor,
    payment_id,
    order_id,
    booking_id,
    gateway_payment_id,
    amount,
    reason
):

    amount = round(float(amount), 2)

    if amount <= 0:
        return {
            "success": False,
            "status": "Refund Failed",
            "message": "Refund amount must be greater than zero."
        }

    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM payment_refunds
        WHERE payment_id = %s
          AND status IN ('Pending', 'Processed')
    """, (
        payment_id,
    ))

    already_requested = float(
        cursor.fetchone()[0] or 0
    )

    cursor.execute("""
        SELECT amount
        FROM payments
        WHERE id = %s
        FOR UPDATE
    """, (
        payment_id,
    ))

    payment_row = cursor.fetchone()

    if not payment_row:
        return {
            "success": False,
            "status": "Refund Failed",
            "message": "Payment record not found."
        }

    payment_amount = float(
        payment_row[0]
    )

    remaining = round(
        payment_amount - already_requested,
        2
    )

    if amount > remaining + 0.001:
        return {
            "success": False,
            "status": "Refund Failed",
            "message": (
                "The requested refund exceeds "
                "the remaining refundable amount."
            )
        }

    try:

        refund = razorpay_client.payment.refund(
            str(gateway_payment_id),
            {
                "amount": int(
                    round(amount * 100)
                ),
                "speed": "normal",

                "receipt":
                    f"rentez-refund-order-"
                    f"{order_id}-"
                    f"{booking_id or 'full'}-"
                    f"{uuid.uuid4().hex[:8]}",

                "notes": {
                    "order_id": str(order_id),
                    "booking_id": str(
                        booking_id or ""
                    ),
                    "reason": reason
                }
            }
        )

    except Exception as e:

        print(
            "Razorpay refund request failed:",
            e
        )

        return {
            "success": False,
            "status": "Refund Failed",
            "message": (
                "Razorpay could not accept "
                "the refund request."
            )
        }

    refund_id = refund.get("id")

    if not refund_id:
        return {
            "success": False,
            "status": "Refund Failed",
            "message": (
                "Razorpay did not return a refund ID."
            )
        }

    gateway_status = str(
        refund.get(
            "status",
            "pending"
        )
    ).lower().strip()

    if gateway_status == "processed":
        status = "Processed"

    elif gateway_status in (
        "failed",
        "rejected"
    ):
        status = "Failed"

    else:
        status = "Pending"

    refund_type = (
        "Full"
        if booking_id is None
        else "Partial"
    )

    cursor.execute("""
        INSERT INTO payment_refunds (
            payment_id,
            order_id,
            booking_id,
            refund_type,
            amount,
            gateway_refund_id,
            status
        )
        VALUES (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s
        )
    """, (
        payment_id,
        order_id,
        booking_id,
        refund_type,
        amount,
        str(refund_id),
        status
    ))

    if status == "Failed":

        local_payment_status = (
            "Refund Failed"
        )

    elif booking_id is None and status == "Processed":

        # Full order refund completed.
        local_payment_status = "Refunded"

    elif booking_id is None and status == "Pending":

        # Full order refund still processing.
        local_payment_status = "Refund Pending"

    else:

        # Business cancelled only one booking inside
        # a multi-item order. The overall payment is
        # still paid because only part was refunded.
        local_payment_status = "Paid"

    cursor.execute("""
        UPDATE payments
        SET
            gateway_refund_id = %s,
            payment_status = %s,

            refund_initiated_at =
                COALESCE(
                    refund_initiated_at,
                    NOW()
                ),

            refunded_at = CASE
                WHEN %s = 'Processed'
                    AND %s IS NULL
                THEN NOW()
                ELSE refunded_at
            END

        WHERE id = %s
    """, (
        str(refund_id),
        local_payment_status,
        status,
        booking_id,
        payment_id
    ))

    return {
        "success": status != "Failed",
        "status": status,
        "refund_id": str(refund_id),
        "amount": amount
    }


def recalculate_order_refund_state(
    cursor,
    order_id
):

    cursor.execute("""
        SELECT
            total_amount,
            payment_status,
            order_status
        FROM orders
        WHERE id = %s
        FOR UPDATE
    """, (
        order_id,
    ))

    order = cursor.fetchone()

    if not order:
        return None

    total_amount = float(
        order[0]
    )

    cursor.execute("""
        SELECT

            COALESCE(
                SUM(
                    CASE
                        WHEN status = 'Processed'
                        THEN amount
                        ELSE 0
                    END
                ),
                0
            ),

            COALESCE(
                SUM(
                    CASE
                        WHEN status = 'Pending'
                        THEN amount
                        ELSE 0
                    END
                ),
                0
            ),

            COALESCE(
                SUM(
                    CASE
                        WHEN status = 'Failed'
                        THEN amount
                        ELSE 0
                    END
                ),
                0
            )

        FROM payment_refunds

        WHERE order_id = %s
    """, (
        order_id,
    ))

    processed, pending, failed = map(
        lambda x: float(x or 0),
        cursor.fetchone()
    )

    cursor.execute("""
        SELECT
            COUNT(*),

            SUM(
                CASE
                    WHEN booking_status = 'Cancelled'
                    THEN 1
                    ELSE 0
                END
            )

        FROM bookings

        WHERE order_id = %s
    """, (
        order_id,
    ))

    counts = cursor.fetchone()

    total_bookings = int(
        counts[0] or 0
    )

    cancelled_bookings = int(
        counts[1] or 0
    )

    all_bookings_cancelled = (
        total_bookings > 0
        and cancelled_bookings == total_bookings
    )


    if not all_bookings_cancelled:

        # Order still contains at least one active booking.
        # Therefore the overall payment remains Paid.

        payment_status = order[1]

    else:

        # Entire order is cancelled, so now the refund state
        # represents the whole order.

        if pending > 0:

            payment_status = (
                "Refund Pending"
            )

        elif processed >= (
            total_amount - 0.01
        ):

            payment_status = "Refunded"

        elif failed > 0:

            payment_status = (
                "Refund Failed"
            )

        else:

            payment_status = order[1]

    order_status = order[2]

    if (
        total_bookings > 0
        and cancelled_bookings == total_bookings
    ):

        order_status = "Cancelled"

    cursor.execute("""
        UPDATE orders
        SET
            payment_status = %s,
            order_status = %s
        WHERE id = %s
    """, (
        payment_status,
        order_status,
        order_id
    ))

    return {
        "payment_status": payment_status,
        "order_status": order_status,
        "processed": processed,
        "pending": pending,
        "failed": failed
    }


@app.route(
    "/cancel-order/<int:order_id>",
    methods=["POST"]
)
def cancel_order(order_id):

    if not customer_logged_in():
        return redirect(url_for("login"))

    cursor = mysql.connection.cursor()

    try:

        cursor.execute("""
            SELECT
                id,
                total_amount,
                payment_status,
                order_status,
                start_date,
                end_date
            FROM orders
            WHERE id = %s
              AND user_id = %s
            FOR UPDATE
        """, (
            order_id,
            session["user_id"]
        ))

        order = cursor.fetchone()

        if not order:
            return "Order not found.", 404

        if order[3] == "Cancelled":
            return redirect(
                url_for("my_rentals")
            )

        cursor.execute("""
            SELECT
                id,
                booking_status,
                payment_status,
                total_amount
            FROM bookings
            WHERE order_id = %s
              AND user_id = %s
            FOR UPDATE
        """, (
            order_id,
            session["user_id"]
        ))

        bookings = cursor.fetchall()

        if not bookings:
            return "Order contains no bookings.", 400

        blocked = {
            "Out for Delivery",
            "Delivered",
            "Returned",
            "Completed"
        }

        if any(
            booking[1] in blocked
            for booking in bookings
        ):

            return (
                "This order cannot be cancelled "
                "because one or more rentals have "
                "already entered fulfilment.",
                400
            )

        # =================================================
        # UNPAID ORDER
        # =================================================

        if order[2] in (
            "Pending",
            "Failed",
            "Cancelled"
        ):

            cursor.execute("""
                UPDATE bookings
                SET
                    booking_status = 'Cancelled',
                    payment_status = 'Cancelled',

                    cancelled_by = 'Customer',

                    cancellation_reason =
                        'Order cancelled by customer'

                WHERE order_id = %s
                  AND user_id = %s

                  AND booking_status NOT IN (
                      'Out for Delivery',
                      'Delivered',
                      'Returned',
                      'Completed'
                  )
            """, (
                order_id,
                session["user_id"]
            ))

            cursor.execute("""
                UPDATE payments
                SET payment_status = 'Cancelled'

                WHERE order_id = %s

                  AND payment_status IN (
                      'Pending',
                      'Failed'
                  )
            """, (
                order_id,
            ))

            cursor.execute("""
                UPDATE payouts
                SET payout_status = 'Cancelled'

                WHERE booking_id IN (
                    SELECT id
                    FROM bookings
                    WHERE order_id = %s
                )

                AND payout_status = 'Held'
            """, (
                order_id,
            ))

            cursor.execute("""
                UPDATE orders
                SET
                    order_status = 'Cancelled',
                    payment_status = 'Cancelled'

                WHERE id = %s
                  AND user_id = %s
            """, (
                order_id,
                session["user_id"]
            ))

            create_notification(
                session["user_id"],
                "order_cancelled",
                "Order Cancelled",
                (
                    f"Your RentEZ order #{order_id} "
                    "has been cancelled."
                ),
                url_for("my_rentals")
            )

            mysql.connection.commit()

            # Email after successful DB commit
            try:

                cursor.execute("""
                    SELECT
                        email,
                        full_name
                    FROM users
                    WHERE id = %s
                """, (
                    session["user_id"],
                ))

                customer = cursor.fetchone()

                if customer and customer[0]:

                    send_email(
                        customer[0],
                        f"RentEZ Order #{order_id} Cancelled",
                        f"""Hello {customer[1]},

Your RentEZ order #{order_id} has been cancelled successfully.

No payment was made for this order.

Regards,
RentEZ Team
"""
                    )

                cursor.execute("""
                    SELECT DISTINCT
                        b.business_email,
                        b.business_name

                    FROM order_items oi

                    JOIN businesses b
                        ON oi.business_id = b.id

                    WHERE oi.order_id = %s

                      AND b.business_email IS NOT NULL
                      AND b.business_email != ''
                """, (
                    order_id,
                ))

                for (
                    business_email,
                    business_name
                ) in cursor.fetchall():

                    send_email(
                        business_email,
                        f"RentEZ Order #{order_id} Cancelled",
                        f"""Hello {business_name},

RentEZ order #{order_id} containing equipment or packages from your business has been cancelled by the customer.

Please check the Business Bookings page for the latest status.

Regards,
RentEZ Team
"""
                    )

            except Exception as email_error:

                print(
                    "Order cancellation email failed:",
                    email_error
                )

            return redirect(
                url_for("my_rentals")
            )

        # =================================================
        # PAID ORDER
        # =================================================

        if order[2] == "Paid":

            cursor.execute("""
                SELECT
                    id,
                    gateway_payment_id,
                    amount

                FROM payments

                WHERE order_id = %s
                  AND gateway = 'Razorpay'

                  AND payment_status IN (
                      'Paid',
                      'Refund Pending'
                  )

                  AND gateway_payment_id IS NOT NULL

                ORDER BY id DESC
                LIMIT 1

                FOR UPDATE
            """, (
                order_id,
            ))

            payment = cursor.fetchone()

            if not payment:

                return (
                    "Original payment could not be found.",
                    400
                )

            payment_id = payment[0]
            gateway_payment_id = str(
                payment[1]
            )

            captured_amount = float(
                payment[2]
            )

            cursor.execute("""
                SELECT
                    COALESCE(SUM(amount), 0)

                FROM payment_refunds

                WHERE payment_id = %s

                  AND status IN (
                      'Pending',
                      'Processed'
                  )
            """, (
                payment_id,
            ))

            already_requested = float(
                cursor.fetchone()[0] or 0
            )

            remaining = round(
                captured_amount
                - already_requested,
                2
            )

            if remaining <= 0:

                refund_state = (
                    recalculate_order_refund_state(
                        cursor,
                        order_id
                    )
                )

            else:

                refund_result = create_order_refund(
                    cursor,
                    payment_id,
                    order_id,
                    None,
                    gateway_payment_id,
                    remaining,
                    "Order cancelled by customer"
                )

                if not refund_result["success"]:

                    mysql.connection.rollback()

                    return (
                        "The refund could not be initiated. "
                        "Your order remains confirmed.",
                        400
                    )

                booking_payment_status = (
                    "Refunded"
                    if refund_result["status"]
                    == "Processed"
                    else "Refund Pending"
                )

                cursor.execute("""
                    UPDATE bookings

                    SET
                        booking_status = 'Cancelled',

                        payment_status = %s,

                        cancelled_by = 'Customer',

                        cancellation_reason =
                            'Order cancelled by customer'

                    WHERE order_id = %s
                      AND user_id = %s
                """, (
                    booking_payment_status,
                    order_id,
                    session["user_id"]
                ))

                cursor.execute("""
                    UPDATE payouts
                    SET payout_status = 'Cancelled'

                    WHERE booking_id IN (
                        SELECT id
                        FROM bookings
                        WHERE order_id = %s
                    )

                    AND payout_status = 'Held'
                """, (
                    order_id,
                ))

                refund_state = (
                    recalculate_order_refund_state(
                        cursor,
                        order_id
                    )
                )

            create_notification(
                session["user_id"],
                "order_cancelled",
                "Order Cancelled",
                (
                    f"Your order #{order_id} "
                    f"has been cancelled. "
                    f"Refund status: "
                    f"{refund_state['payment_status']}."
                ),
                url_for("my_rentals")
            )

            mysql.connection.commit()

            try:

                cursor.execute("""
                    SELECT
                        email,
                        full_name
                    FROM users
                    WHERE id = %s
                """, (
                    session["user_id"],
                ))

                customer = cursor.fetchone()

                if customer and customer[0]:

                    send_email(
                        customer[0],
                        f"RentEZ Order #{order_id} Cancelled",
                        f"""Hello {customer[1]},

Your RentEZ order #{order_id} has been cancelled.

Refund status: {refund_state['payment_status']}

Please check My Rentals for the latest information.

Regards,
RentEZ Team
"""
                    )

                cursor.execute("""
                    SELECT DISTINCT
                        b.business_email,
                        b.business_name

                    FROM order_items oi

                    JOIN businesses b
                        ON oi.business_id = b.id

                    WHERE oi.order_id = %s

                      AND b.business_email IS NOT NULL
                      AND b.business_email != ''
                """, (
                    order_id,
                ))

                for (
                    business_email,
                    business_name
                ) in cursor.fetchall():

                    send_email(
                        business_email,
                        f"RentEZ Order #{order_id} Cancelled",
                        f"""Hello {business_name},

RentEZ order #{order_id} has been cancelled by the customer.

Refund status: {refund_state['payment_status']}

Please check the Business Bookings page for the latest information.

Regards,
RentEZ Team
"""
                    )

            except Exception as email_error:

                print(
                    "Order cancellation email failed:",
                    email_error
                )

            return redirect(
                url_for("my_rentals")
            )

        return (
            "This order cannot be cancelled "
            "in its current state.",
            400
        )

    except Exception as e:

        mysql.connection.rollback()

        print(
            "Order cancellation failed:",
            e
        )

        return (
            "Unable to cancel order.",
            500
        )

    finally:

        cursor.close()

@app.route(
    '/business/cancel-booking/<int:booking_id>',
    methods=['POST']
)
def business_cancel_booking(booking_id):

    if (
        "user_id" not in session
        or session.get("user_type") != "Business"
        or "business_id" not in session
    ):
        return jsonify({
            "success": False,
            "message": "Please log in as a business."
        }), 401

    business_id = session["business_id"]

    cursor = mysql.connection.cursor()

    try:

        # =====================================================
        # GET BOOKING + BUSINESS OWNERSHIP + PAYMENT
        # =====================================================

        cursor.execute("""
            SELECT
                b.id,
                b.order_id,
                b.booking_status,
                b.payment_status,
                b.total_amount,
                b.user_id,

                u.email,
                u.full_name,

                p.id,
                p.gateway_payment_id,
                p.amount

            FROM bookings b

            LEFT JOIN equipment e
                ON b.equipment_id = e.id

            LEFT JOIN packages pkg
                ON b.package_id = pkg.id

            JOIN users u
                ON b.user_id = u.id

            LEFT JOIN payments p
                ON (
                    (
                        b.order_id IS NOT NULL
                        AND p.order_id = b.order_id
                    )
                    OR
                    (
                        b.order_id IS NULL
                        AND p.booking_id = b.id
                    )
                )
                AND p.payment_status IN (
                    'Paid',
                    'Refund Pending'
                )

            WHERE b.id = %s
              AND (
                    e.business_id = %s
                    OR pkg.business_id = %s
              )

            ORDER BY p.id DESC

            LIMIT 1

            FOR UPDATE
        """, (
            booking_id,
            business_id,
            business_id
        ))

        booking = cursor.fetchone()

        if not booking:

            return jsonify({
                "success": False,
                "message": "Booking not found."
            }), 404


        booking_order_id = booking[1]
        booking_status = booking[2]
        payment_status = booking[3]
        total_amount = float(booking[4])

        customer_user_id = booking[5]
        customer_email = booking[6]
        customer_name = booking[7]

        payment_id = booking[8]
        gateway_payment_id = booking[9]
        payment_amount = (
            float(booking[10])
            if booking[10] is not None
            else total_amount
        )


        # =====================================================
        # ONLY CONFIRMED BOOKINGS
        # =====================================================

        if booking_status != "Confirmed":

            return jsonify({
                "success": False,
                "message": (
                    "Only confirmed bookings can be "
                    "cancelled by the business."
                )
            }), 400


        # =====================================================
        # UNPAID
        # =====================================================

        if payment_status == "Pending":

            cursor.execute("""
                UPDATE bookings

                SET
                    booking_status = 'Cancelled',
                    payment_status = 'Cancelled',
                    cancelled_by = 'Business',
                    cancellation_reason =
                        'Cancelled by business'

                WHERE id = %s
                  AND booking_status = 'Confirmed'
                  AND payment_status = 'Pending'
            """, (
                booking_id,
            ))

            cursor.execute("""
                UPDATE payouts

                SET payout_status = 'Cancelled'

                WHERE booking_id = %s
                  AND payout_status = 'Held'
            """, (
                booking_id,
            ))

            create_notification(
                customer_user_id,
                "booking_cancelled",
                "Booking Cancelled by Business",
                (
                    f"Booking #{booking_id} was "
                    "cancelled by the business."
                ),
                url_for("my_rentals")
            )

            mysql.connection.commit()

            if customer_email:

                send_email(
                    customer_email,
                    f"RentEZ Booking #{booking_id} Cancelled",
                    f"""Hello {customer_name},

Your RentEZ booking #{booking_id} was cancelled by the business.

No payment was made for this booking.

Regards,
RentEZ Team
"""
                )

            return jsonify({
                "success": True,
                "payment_status": "Cancelled"
            })


        # =====================================================
        # PAID
        # =====================================================

        if (
            payment_status in (
                "Paid",
                "Refund Pending"
            )
            and payment_id
            and gateway_payment_id
        ):

            # -------------------------------------------------
            # Refund only this booking's amount
            # -------------------------------------------------

            refund_result = create_order_refund(
                cursor,
                payment_id,
                booking_order_id,
                booking_id,
                gateway_payment_id,
                payment_amount
                if booking_order_id is None
                else total_amount,
                "Booking cancelled by business"
            )

            if not refund_result["success"]:

                return jsonify({
                    "success": False,
                    "message": (
                        refund_result.get(
                            "message",
                            "The refund could not be initiated."
                        )
                    )
                }), 400


            if refund_result["status"] == "Processed":

                booking_refund_status = "Refunded"

            elif refund_result["status"] == "Pending":

                booking_refund_status = (
                    "Refund Pending"
                )

            else:

                booking_refund_status = (
                    "Refund Failed"
                )


            # -------------------------------------------------
            # Cancel this booking
            # -------------------------------------------------

            cursor.execute("""
                UPDATE bookings

                SET
                    booking_status = 'Cancelled',
                    payment_status = %s,
                    cancelled_by = 'Business',
                    cancellation_reason =
                        'Cancelled by business'

                WHERE id = %s
                  AND booking_status = 'Confirmed'
            """, (
                booking_refund_status,
                booking_id
            ))


            # -------------------------------------------------
            # Release its stock reservation
            # The item was never sent out yet.
            # -------------------------------------------------

            cursor.execute("""
                UPDATE payouts

                SET payout_status = 'Cancelled'

                WHERE booking_id = %s
                  AND payout_status = 'Held'
            """, (
                booking_id,
            ))


            # -------------------------------------------------
            # Recalculate order-level state
            # -------------------------------------------------

            if booking_order_id is not None:

                order_state = (
                    recalculate_order_refund_state(
                        cursor,
                        booking_order_id
                    )
                )

            else:

                order_state = {
                    "payment_status":
                        booking_refund_status
                }


            create_notification(
                customer_user_id,
                "booking_cancelled",
                "Booking Cancelled by Business",
                (
                    f"Booking #{booking_id} was "
                    f"cancelled by the business. "
                    f"Refund status: "
                    f"{booking_refund_status}."
                ),
                url_for("my_rentals")
            )

            mysql.connection.commit()


            # -------------------------------------------------
            # CUSTOMER EMAIL
            # -------------------------------------------------

            if customer_email:

                send_email(
                    customer_email,
                    f"RentEZ Booking #{booking_id} Cancelled",
                    f"""Hello {customer_name},

Your RentEZ booking #{booking_id} was cancelled by the business.

Refund status:
{booking_refund_status}

Please check My Rentals for the latest information.

Regards,
RentEZ Team
"""
                )


            return jsonify({
                "success": True,

                "payment_status":
                    booking_refund_status,

                "order_payment_status":
                    order_state["payment_status"]
            })


        return jsonify({
            "success": False,
            "message": (
                "This booking cannot be cancelled "
                "in its current payment state."
            )
        }), 400


    except Exception as e:

        mysql.connection.rollback()

        print(
            "Business booking cancellation failed:",
            e
        )

        return jsonify({
            "success": False,
            "message":
                "Unable to cancel booking."
        }), 500

    finally:

        cursor.close()


@app.route('/business/delete-equipment/<int:equipment_id>', methods=['POST'])
def delete_equipment(equipment_id):

    if (
        "user_id" not in session
        or session.get("user_type") != "Business"
        or "business_id" not in session
    ):
        return jsonify({
            "success": False,
            "message": "Please log in as a business."
        }), 401

    business_id = session["business_id"]

    cursor = mysql.connection.cursor()


    # =====================================================
    # VERIFY OWNERSHIP
    # =====================================================

    cursor.execute("""
        SELECT
            id,
            name,
            image,
            is_active
        FROM equipment
        WHERE id = %s
            AND business_id = %s
    """, (
        equipment_id,
        business_id
    ))

    equipment = cursor.fetchone()

    if not equipment:

        return jsonify({
            "success": False,
            "message": "Equipment not found."
        }), 404

    # =====================================================
    # CHECK ALL REFERENCES
    # =====================================================

    cursor.execute("""
        SELECT COUNT(*)
        FROM bookings
        WHERE equipment_id = %s
    """, (
        equipment_id,
    ))

    booking_count = int(
        cursor.fetchone()[0]
    )

    cursor.execute("""
        SELECT COUNT(*)
        FROM booking_items
        WHERE equipment_id = %s
    """, (
        equipment_id,
    ))

    booking_item_count = int(
        cursor.fetchone()[0]
    )

    cursor.execute("""
        SELECT COUNT(*)
        FROM package_items
        WHERE equipment_id = %s
    """, (
        equipment_id,
    ))

    package_item_count = int(
        cursor.fetchone()[0]
    )

    has_history = (
        booking_count > 0
        or booking_item_count > 0
        or package_item_count > 0
    )

    # =====================================================
    # REFERENCED EQUIPMENT → ARCHIVE
    # =====================================================

    if has_history:

        cursor.execute("""
            UPDATE equipment
            SET
                is_active = FALSE,
                available = FALSE
            WHERE id = %s
            AND business_id = %s
        """, (
            equipment_id,
            business_id
        ))

        mysql.connection.commit()

        return jsonify({
            "success": True,
            "action": "archived",
            "message": (
                f'"{equipment[1]}" has been archived and '
                "removed from customer listings."
            )
        })

    # =====================================================
    # NEVER REFERENCED → PERMANENT DELETE
    # =====================================================

    cursor.execute("""
        DELETE FROM equipment
        WHERE id = %s
        AND business_id = %s
    """, (
        equipment_id,
        business_id
    ))

    mysql.connection.commit()

    return jsonify({
        "success": True,
        "action": "deleted",
        "message": "Equipment deleted successfully."
    })


        
@app.route(
    '/business/toggle-equipment/<int:equipment_id>',
    methods=['POST']
)
def toggle_equipment(equipment_id):

    if (
        "user_id" not in session
        or session.get("user_type") != "Business"
        or "business_id" not in session
    ):
        return jsonify({
            "success": False,
            "message": "Please log in as a business."
        }), 401

    business_id = session["business_id"]

    cursor = mysql.connection.cursor()

    try:

        cursor.execute("""
            SELECT
                id,
                name,
                is_active,
                available_quantity,
                total_quantity
            FROM equipment
            WHERE id = %s
              AND business_id = %s
        """, (
            equipment_id,
            business_id
        ))

        equipment = cursor.fetchone()

        if not equipment:

            return jsonify({
                "success": False,
                "message": "Equipment not found."
            }), 404

        current_active = bool(equipment[2])

        # =====================================================
        # DEACTIVATE
        # =====================================================

        if current_active:

            cursor.execute("""
                UPDATE equipment
                SET
                    is_active = FALSE,
                    available = FALSE
                WHERE id = %s
                  AND business_id = %s
            """, (
                equipment_id,
                business_id
            ))

            mysql.connection.commit()

            return jsonify({
                "success": True,
                "active": False,
                "message": (
                    f'"{equipment[1]}" has been deactivated.'
                )
            })

        # =====================================================
        # REACTIVATE
        # =====================================================

        available_quantity = int(equipment[3] or 0)

        new_available = (
            available_quantity > 0
        )

        cursor.execute("""
            UPDATE equipment
            SET
                is_active = TRUE,
                available = %s
            WHERE id = %s
              AND business_id = %s
        """, (
            new_available,
            equipment_id,
            business_id
        ))

        mysql.connection.commit()

        return jsonify({
            "success": True,
            "active": True,
            "available": new_available,
            "message": (
                f'"{equipment[1]}" has been reactivated.'
            )
        })

    except Exception as e:

        mysql.connection.rollback()

        print("Equipment status update failed:", e)

        return jsonify({
            "success": False,
            "message": "Unable to update equipment status."
        }), 500

    finally:
        cursor.close()

@app.route(
    "/business-profile",
    methods=["GET", "POST"]
)
def business_profile():

    if (
        "user_id" not in session
        or session.get("user_type") != "Business"
        or "business_id" not in session
    ):
        return redirect(url_for("business_login"))

    business_id = session["business_id"]
    user_id = session["user_id"]

    cursor = mysql.connection.cursor()

    try:

        # =================================================
        # CURRENT BUSINESS
        # =================================================

        cursor.execute("""
            SELECT
                b.id,
                b.business_name,
                b.business_email,
                b.business_phone,
                b.registration_number,
                b.address,
                b.city,
                b.description,
                b.approval_status,
                b.rejection_reason,
                u.email,
                u.phone
            FROM businesses b
            JOIN users u
                ON u.id = b.user_id
            WHERE b.id = %s
              AND b.user_id = %s
        """, (
            business_id,
            user_id
        ))

        business = cursor.fetchone()

        if not business:

            session.clear()

            return redirect(
                url_for("business_login")
            )

        approval_status = business[8]

        # =================================================
        # CURRENT VERIFICATION DOCUMENT
        # =================================================

        cursor.execute("""
            SELECT
                id,
                document_type,
                document_path
            FROM business_documents
            WHERE business_id = %s
            ORDER BY id DESC
            LIMIT 1
        """, (
            business_id,
        ))

        document = cursor.fetchone()

        # =================================================
        # POST
        # =================================================

        if request.method == "POST":

            business_email = request.form.get(
                "business_email",
                ""
            ).strip().lower()

            business_phone = request.form.get(
                "business_phone",
                ""
            ).strip()

            address = request.form.get(
                "address",
                ""
            ).strip()

            city = request.form.get(
                "city",
                ""
            ).strip()

            description = request.form.get(
                "description",
                ""
            ).strip()

            resubmit = (
                request.form.get(
                    "resubmit_application"
                ) == "1"
            )

            # -------------------------------------------------
            # BUSINESS NAME
            # -------------------------------------------------
            # Registration number is permanently immutable.
            # Business name becomes editable only after approval.
            
            if approval_status == "Approved":
                business_name = request.form.get("business_name", "").strip()
            else:
                business_name = business[1]

            # -------------------------------------------------
            # VALIDATION
            # -------------------------------------------------

            if not business_name:

                return render_template(
                    "business_profile.html",
                    business=business,
                    document=document,
                    profile_error=(
                        "Business name is required."
                    )
                )

            if not business_email:

                return render_template(
                    "business_profile.html",
                    business=business,
                    document=document,
                    profile_error=(
                        "Business email is required."
                    )
                )

            if "@" not in business_email:

                return render_template(
                    "business_profile.html",
                    business=business,
                    document=document,
                    profile_error=(
                        "Please enter a valid email address."
                    )
                )

            if (
                not business_phone.isdigit()
                or len(business_phone) != 10
            ):

                return render_template(
                    "business_profile.html",
                    business=business,
                    document=document,
                    profile_error=(
                        "Please enter a valid 10-digit phone number."
                    )
                )

            if not address:

                return render_template(
                    "business_profile.html",
                    business=business,
                    document=document,
                    profile_error=(
                        "Business address is required."
                    )
                )

            if not city:

                return render_template(
                    "business_profile.html",
                    business=business,
                    document=document,
                    profile_error=(
                        "City is required."
                    )
                )

            # -------------------------------------------------
            # RESUBMISSION IS ONLY ALLOWED AFTER REJECTION
            # -------------------------------------------------

            if resubmit and approval_status != "Rejected":

                return render_template(
                    "business_profile.html",
                    business=business,
                    document=document,
                    profile_error=(
                        "Only a rejected application can be "
                        "resubmitted."
                    )
                )

            # -------------------------------------------------
            # RESUBMISSION REQUIRES A NEW DOCUMENT
            # -------------------------------------------------

            new_document = request.files.get(
                "verification_document"
            )

            document_type = request.form.get(
                "document_type",
                ""
            ).strip()

            if resubmit:

                if not new_document:

                    return render_template(
                        "business_profile.html",
                        business=business,
                        document=document,
                        profile_error=(
                            "Please upload a new verification "
                            "document before resubmitting."
                        )
                    )

                if not document_type:

                    return render_template(
                        "business_profile.html",
                        business=business,
                        document=document,
                        profile_error=(
                            "Please select a verification "
                            "document type."
                        )
                    )

                filename = secure_filename(
                    new_document.filename
                )

                extension = get_file_extension(
                    filename
                )

                if (
                    not filename
                    or extension not in ALLOWED_BUSINESS_DOCUMENTS
                ):

                    return render_template(
                        "business_profile.html",
                        business=business,
                        document=document,
                        profile_error=(
                            "Only PDF, JPG, JPEG and PNG "
                            "documents are allowed."
                        )
                    )

                new_document.stream.seek(
                    0,
                    os.SEEK_END
                )

                document_size = (
                    new_document.stream.tell()
                )

                new_document.stream.seek(0)

                if (
                    document_size
                    > MAX_BUSINESS_DOCUMENT_SIZE
                ):

                    return render_template(
                        "business_profile.html",
                        business=business,
                        document=document,
                        profile_error=(
                            "Verification document must be "
                            "10 MB or smaller."
                        )
                    )

                if not valid_file_signature(
                    new_document,
                    extension
                ):

                    return render_template(
                        "business_profile.html",
                        business=business,
                        document=document,
                        profile_error=(
                            "The uploaded document is invalid "
                            "or does not match its file type."
                        )
                    )

            # -------------------------------------------------
            # EMAIL UNIQUENESS
            # -------------------------------------------------

            cursor.execute("""
                SELECT id
                FROM users
                WHERE email = %s
                  AND id <> %s
                LIMIT 1
            """, (
                business_email,
                user_id
            ))

            if cursor.fetchone():

                return render_template(
                    "business_profile.html",
                    business=business,
                    document=document,
                    profile_error=(
                        "This email address is already "
                        "associated with another account."
                    )
                )

            # -------------------------------------------------
            # PHONE UNIQUENESS
            # -------------------------------------------------

            cursor.execute("""
                SELECT id
                FROM users
                WHERE phone = %s
                  AND id <> %s
                LIMIT 1
            """, (
                business_phone,
                user_id
            ))

            if cursor.fetchone():

                return render_template(
                    "business_profile.html",
                    business=business,
                    document=document,
                    profile_error=(
                        "This phone number is already "
                        "associated with another account."
                    )
                )

            # -------------------------------------------------
            # UPDATE USER
            # -------------------------------------------------

            cursor.execute("""
                UPDATE users
                SET
                    email = %s,
                    phone = %s
                WHERE id = %s
                  AND user_type = 'Business'
            """, (
                business_email,
                business_phone,
                user_id
            ))

            # -------------------------------------------------
            # UPDATE BUSINESS
            # -------------------------------------------------

            new_status = (
                "Pending"
                if resubmit
                else approval_status
            )

            cursor.execute("""
                UPDATE businesses
                SET
                    business_name = %s,
                    business_email = %s,
                    business_phone = %s,
                    address = %s,
                    city = %s,
                    description = %s,
                    approval_status = %s,
                    rejection_reason = %s
                WHERE id = %s
                  AND user_id = %s
            """, (
                business_name,
                business_email,
                business_phone,
                address,
                city,
                description,
                new_status,
                None if resubmit else business[9],
                business_id,
                user_id
            ))

            # =================================================
            # REPLACE VERIFICATION DOCUMENT ON RESUBMISSION
            # =================================================

            if resubmit:

                unique_filename = (
                    f"business_{business_id}_"
                    f"{uuid.uuid4().hex}."
                    f"{extension}"
                )

                new_document_path = os.path.join(
                    BUSINESS_DOCUMENT_FOLDER,
                    unique_filename
                )

                new_document.save(
                    new_document_path
                )

                relative_path = (
                    "uploads/business_documents/"
                    f"{unique_filename}"
                )

                if document:

                    cursor.execute("""
                        UPDATE business_documents
                        SET
                            document_type = %s,
                            document_path = %s,
                            uploaded_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (
                        document_type,
                        relative_path,
                        document[0]
                    ))

                    old_path = document[2]

                    old_absolute_path = os.path.join(
                        app.root_path,
                        old_path
                    )

                    if (
                        os.path.abspath(old_absolute_path)
                        != os.path.abspath(new_document_path)
                        and os.path.isfile(old_absolute_path)
                    ):

                        try:
                            os.remove(
                                old_absolute_path
                            )
                        except OSError:
                            pass

                else:

                    cursor.execute("""
                        INSERT INTO business_documents
                        (
                            business_id,
                            document_type,
                            document_path
                        )
                        VALUES (%s, %s, %s)
                    """, (
                        business_id,
                        document_type,
                        relative_path
                    ))

            mysql.connection.commit()

            # =================================================
            # ADMIN NOTIFICATION ON RESUBMISSION
            # =================================================

            if resubmit:

                admin_cursor = mysql.connection.cursor()

                try:

                    admin_cursor.execute("""
                        SELECT
                            id,
                            email
                        FROM users
                        WHERE user_type = 'Admin'
                          AND email IS NOT NULL
                          AND email != ''
                    """)

                    admins = admin_cursor.fetchall()

                finally:

                    admin_cursor.close()

                for admin_id, admin_email in admins:

                    create_notification(
                        admin_id,
                        "business_resubmitted",
                        "Business Application Resubmitted",
                        (
                            f"{business_name} has resubmitted "
                            f"their business application for review."
                        ),
                        url_for(
                            "admin_business_detail",
                            business_id=business_id
                        )
                    )

                    send_email(
                        admin_email,
                        "Business Application Resubmitted - RentEZ",
                        f"""A business application has been resubmitted.

                        Business Name:
                        {business_name}

                        Owner:
                        {session["user_name"]}

                        Registration Number:
                        {business[4]}

                        City:
                        {city}

                        Status:
                        Pending

                        Please review the application in the RentEZ Admin Panel.
                        """
                    )
                mysql.connection.commit()

                # Refresh business data
                cursor.execute("""
                    SELECT
                        b.id,
                        b.business_name,
                        b.business_email,
                        b.business_phone,
                        b.registration_number,
                        b.address,
                        b.city,
                        b.description,
                        b.approval_status,
                        b.rejection_reason,
                        u.email,
                        u.phone
                    FROM businesses b
                    JOIN users u
                        ON u.id = b.user_id
                    WHERE b.id = %s
                      AND b.user_id = %s
                """, (
                    business_id,
                    user_id
                ))

                business = cursor.fetchone()

                cursor.execute("""
                    SELECT
                        id,
                        document_type,
                        document_path
                    FROM business_documents
                    WHERE business_id = %s
                    ORDER BY id DESC
                    LIMIT 1
                """, (
                    business_id,
                ))

                document = cursor.fetchone()

                return redirect(
                    url_for("business_status")
                )

            # Normal profile save
            cursor.execute("""
                SELECT
                    b.id,
                    b.business_name,
                    b.business_email,
                    b.business_phone,
                    b.registration_number,
                    b.address,
                    b.city,
                    b.description,
                    b.approval_status,
                    b.rejection_reason,
                    u.email,
                    u.phone
                FROM businesses b
                JOIN users u
                    ON u.id = b.user_id
                WHERE b.id = %s
                  AND b.user_id = %s
            """, (
                business_id,
                user_id
            ))

            business = cursor.fetchone()

            return render_template(
                "business_profile.html",
                business=business,
                document=document,
                profile_success=(
                    "Business profile updated successfully."
                )
            )

        return render_template(
            "business_profile.html",
            business=business,
            document=document
        )

    except Exception as e:

        mysql.connection.rollback()

        print(
            "Business profile update failed:",
            e
        )

        return render_template(
            "business_profile.html",
            business=business if "business" in locals() else None,
            document=document if "document" in locals() else None,
            profile_error=(
                "Unable to update your profile right now. "
                "Please try again."
            )
        )

    finally:
        cursor.close()
    
@app.route('/business-settings')
def business_settings():

    if (
        "user_id" not in session
        or session.get("user_type") != "Business"
        or "business_id" not in session
    ):
        return redirect(url_for("business_login"))

    return render_template(
        'business_settings.html'
    )
    
    
@app.route('/change-business-password', methods=['POST'])
def change_business_password():

    if (
        "user_id" not in session
        or session.get("user_type") != "Business"
        or "business_id" not in session
    ):
        return redirect(url_for("business_login"))

    business_id = session['business_id']

    current_password = request.form.get(
        'current_password',
        ''
    )

    new_password = request.form.get(
        'new_password',
        ''
    )

    confirm_password = request.form.get(
        'confirm_password',
        ''
    )


    # =========================
    # VALIDATION
    # =========================

    if not current_password or not new_password or not confirm_password:

        return render_template(
            'business_settings.html',
            password_error="Please fill in all password fields."
        )


    if len(new_password) < 6:

        return render_template(
            'business_settings.html',
            password_error="New password must be at least 6 characters long."
        )


    if new_password != confirm_password:

        return render_template(
            'business_settings.html',
            password_error="New passwords do not match."
        )


    # =========================
    # GET CURRENT PASSWORD
    # =========================

    cursor = mysql.connection.cursor()

    cursor.execute("""
        SELECT
            u.id,
            u.password
        FROM users u
        JOIN businesses b
            ON b.user_id = u.id
        WHERE b.id = %s
    """, (business_id,))

    user = cursor.fetchone()


    if not user:

        cursor.close()

        return redirect(
            url_for('business_login')
        )


    user_id = user[0]
    stored_password = user[1]


    # =========================
    # CHECK CURRENT PASSWORD
    # =========================

    if not check_password_hash(
        stored_password,
        current_password
    ):

        cursor.close()

        return render_template(
            'business_settings.html',
            password_error="Current password is incorrect."
        )


    # =========================
    # UPDATE PASSWORD
    # =========================

    hashed_password = generate_password_hash(
        new_password
    )

    cursor.execute("""
        UPDATE users
        SET password = %s
        WHERE id = %s
    """, (
        hashed_password,
        user_id
    ))

    mysql.connection.commit()

    cursor.close()


    return render_template(
        'business_settings.html',
        password_success="Your password has been changed successfully."
    )


@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():

    if request.method == "GET":

        return render_template(
            "admin_login.html"
        )


    email = request.form.get(
        "email",
        ""
    ).strip()

    password = request.form.get(
        "password",
        ""
    )


    if not email or not password:

        return render_template(
            "admin_login.html",
            login_error=
                "Please enter your email and password."
        )


    cursor = mysql.connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            full_name,
            email,
            password,
            user_type
        FROM users
        WHERE email = %s
          AND user_type = 'Admin'
        """,
        (email,)
    )

    admin = cursor.fetchone()

    cursor.close()


    if not admin:

        return render_template(
            "admin_login.html",
            login_error=
                "Invalid admin email or password."
        )


    if not check_password_hash(
        admin[3],
        password
    ):

        return render_template(
            "admin_login.html",
            login_error=
                "Invalid admin email or password."
        )


    session.clear()

    session.permanent = True

    session["user_id"] = admin[0]
    session["user_name"] = admin[1]
    session["user_type"] = "Admin"

    return redirect(
        url_for("admin_dashboard")
    )


# =========================================================
# ADMIN AUTHORIZATION
# =========================================================

def admin_logged_in():

    return (
        "user_id" in session
        and session.get("user_type") == "Admin"
    )


@app.route("/admin-dashboard")
def admin_dashboard():

    if not admin_logged_in():
        return redirect(url_for("admin_login"))

    cursor = mysql.connection.cursor()

    try:

        # =====================================================
        # BUSINESSES
        # =====================================================

        cursor.execute("""
            SELECT
                b.id,
                b.business_name,
                b.business_email,
                b.business_phone,
                b.registration_number,
                b.address,
                b.city,
                b.description,
                b.approval_status,
                b.rejection_reason
            FROM businesses b
            ORDER BY
                CASE
                    WHEN b.approval_status = 'Pending' THEN 1
                    WHEN b.approval_status = 'Approved' THEN 2
                    WHEN b.approval_status = 'Rejected' THEN 3
                    ELSE 4
                END,
                b.id DESC
        """)

        businesses = cursor.fetchall()


        # =====================================================
        # DOCUMENTS
        # =====================================================

        cursor.execute("""
            SELECT
                id,
                business_id,
                document_type,
                document_path
            FROM business_documents
            ORDER BY uploaded_at DESC
        """)

        documents = cursor.fetchall()

        business_documents = {}

        for document in documents:

            business_id = document[1]

            if business_id not in business_documents:
                business_documents[business_id] = []

            business_documents[business_id].append({
                "id": document[0],
                "type": document[2],
                "path": document[3]
            })


        # =====================================================
        # VERIFICATION HISTORY
        # =====================================================

        cursor.execute("""
            SELECT
                a.id,
                a.business_id,
                a.old_status,
                a.new_status,
                a.rejection_reason,
                a.created_at,
                u.full_name,
                u.email
            FROM business_verification_audit a
            JOIN users u
                ON a.admin_user_id = u.id
            ORDER BY a.created_at DESC
        """)

        audit_rows = cursor.fetchall()

        business_audit_history = {}

        for audit in audit_rows:

            business_id = audit[1]

            if business_id not in business_audit_history:
                business_audit_history[business_id] = []

            business_audit_history[business_id].append({
                "id": audit[0],
                "old_status": audit[2],
                "new_status": audit[3],
                "reason": audit[4],
                "created_at": audit[5],
                "admin_name": audit[6],
                "admin_email": audit[7]
            })


        # =====================================================
        # EQUIPMENT
        # =====================================================

        cursor.execute("""
            SELECT
                e.id,
                e.name,
                e.category,
                e.price_per_day,
                e.total_quantity,
                e.available_quantity,
                e.available,
                e.is_active,
                e.created_at,
                b.business_name
            FROM equipment e
            JOIN businesses b
                ON e.business_id = b.id
            ORDER BY e.created_at DESC
        """)

        admin_equipment = cursor.fetchall()


        # =====================================================
        # BOOKINGS
        # =====================================================

        cursor.execute("""
            SELECT
                b.id,
                b.order_id,
                b.start_date,
                b.end_date,
                b.quantity,
                b.daily_rate,

                COALESCE(
                    o.total_amount,
                    b.total_amount
                ) AS total_amount,

                b.booking_status,
                b.payment_status,

                COALESCE(
                    e.name,
                    pkg.name
                ) AS item_name,

                COALESCE(
                    bs.business_name,
                    pkg_business.business_name
                ) AS business_name,

                u.full_name,
                u.email

            FROM bookings b

            LEFT JOIN orders o
                ON b.order_id = o.id

            LEFT JOIN equipment e
                ON b.equipment_id = e.id

            LEFT JOIN packages pkg
                ON b.package_id = pkg.id

            LEFT JOIN businesses bs
                ON e.business_id = bs.id

            LEFT JOIN businesses pkg_business
                ON pkg.business_id = pkg_business.id

            JOIN users u
                ON b.user_id = u.id

            ORDER BY b.created_at DESC
        """)

        admin_bookings = cursor.fetchall()


        # =====================================================
        # CUSTOMERS
        # =====================================================

        cursor.execute("""
            SELECT
                u.id,
                u.full_name,
                u.email,
                u.phone,
                u.created_at
            FROM users u
            WHERE u.user_type = 'Customer'
            ORDER BY u.created_at DESC
        """)

        customers = cursor.fetchall()


        # =====================================================
        # PAYMENTS
        # =====================================================

        cursor.execute("""
            SELECT
                p.id,
                p.booking_id,
                p.order_id,
                p.amount,
                p.currency,
                p.payment_status,
                p.gateway_payment_id,
                p.created_at,

                u.full_name,

                COALESCE(
                    bs.business_name,
                    pkg_business.business_name,
                    (
                        SELECT GROUP_CONCAT(
                            DISTINCT ob.business_name
                            ORDER BY ob.business_name
                            SEPARATOR ', '
                        )
                        FROM order_items oi2
                        JOIN businesses ob
                            ON oi2.business_id = ob.id
                        WHERE oi2.order_id = p.order_id
                    )
                ) AS business_name

            FROM payments p

            LEFT JOIN bookings b
                ON p.booking_id = b.id

            LEFT JOIN orders o
                ON p.order_id = o.id

            LEFT JOIN equipment e
                ON b.equipment_id = e.id

            LEFT JOIN packages pkg
                ON b.package_id = pkg.id

            LEFT JOIN users u
                ON u.id = COALESCE(
                    b.user_id,
                    o.user_id
                )

            LEFT JOIN businesses bs
                ON e.business_id = bs.id

            LEFT JOIN businesses pkg_business
                ON pkg.business_id = pkg_business.id

            ORDER BY p.created_at DESC
        """)

        admin_payments = cursor.fetchall()


        # =====================================================
        # PAYOUTS
        # =====================================================

        cursor.execute("""
            SELECT
                p.id,
                p.booking_id,
                p.business_id,
                p.gross_amount,
                p.commission_amount,
                p.amount,
                p.currency,
                p.payout_status,
                p.payout_reference,
                p.created_at,
                b.business_name
            FROM payouts p
            JOIN businesses b
                ON p.business_id = b.id
            ORDER BY p.created_at DESC
        """)

        admin_payouts = cursor.fetchall()


        # =====================================================
        # BASIC STATISTICS
        # =====================================================

        pending_count = sum(
            1 for business in businesses
            if business[8] == "Pending"
        )

        approved_count = sum(
            1 for business in businesses
            if business[8] == "Approved"
        )

        rejected_count = sum(
            1 for business in businesses
            if business[8] == "Rejected"
        )

        total_equipment = len(admin_equipment)

        active_equipment = sum(
            1 for item in admin_equipment
            if item[7] == 1
        )

        total_bookings = len(admin_bookings)


        # =====================================================
        # FINANCIAL STATISTICS
        # =====================================================

        gross_revenue = sum(
            float(payout[3] or 0)
            for payout in admin_payouts
            if payout[7] in ("Held", "Released")
        )

        platform_revenue = sum(
            float(payout[4] or 0)
            for payout in admin_payouts
            if payout[7] in ("Held", "Released")
        )

        held_payouts = sum(
            float(payout[5] or 0)
            for payout in admin_payouts
            if payout[7] == "Held"
        )

        released_payouts = sum(
            float(payout[5] or 0)
            for payout in admin_payouts
            if payout[7] == "Released"
        )

        refunded_amount = sum(
            float(payment[3] or 0)
            for payment in admin_payments
            if payment[5] == "Refunded"
        )

        refund_count = sum(
            1
            for payment in admin_payments
            if payment[5] == "Refunded"
        )

        total_business_payouts = (
            held_payouts +
            released_payouts
        )


        return render_template(
            "admin_dashboard.html",

            businesses=businesses,
            business_documents=business_documents,
            business_audit_history=business_audit_history,

            admin_equipment=admin_equipment,
            admin_bookings=admin_bookings,
            customers=customers,
            admin_payments=admin_payments,
            admin_payouts=admin_payouts,

            pending_count=pending_count,
            approved_count=approved_count,
            rejected_count=rejected_count,

            total_equipment=total_equipment,
            active_equipment=active_equipment,
            total_bookings=total_bookings,

            gross_revenue=gross_revenue,
            platform_revenue=platform_revenue,
            held_payouts=held_payouts,
            released_payouts=released_payouts,
            total_business_payouts=total_business_payouts,

            refunded_amount=refunded_amount,
            refund_count=refund_count,

            platform_commission_rate=(
                PLATFORM_COMMISSION_RATE * 100
            ),

            admin_name=session["user_name"]
        )

    finally:
        cursor.close()



@app.route(
    "/admin/business/<int:business_id>/approve",
    methods=["POST"]
)
def approve_business(business_id):

    if not admin_logged_in():

        return redirect(
            url_for("admin_login")
        )


    admin_user_id = session["user_id"]

    cursor = mysql.connection.cursor()

    try:

        cursor.execute("""
            SELECT
                id,
                business_name,
                business_email,
                user_id,
                approval_status
            FROM businesses
            WHERE id = %s
            FOR UPDATE
        """, (
            business_id,
        ))

        business = cursor.fetchone()


        if not business:

            mysql.connection.rollback()

            return "Business not found.", 404


        business_name = business[1]
        business_email = business[2]
        business_user_id = business[3]
        current_status = business[4]


        if current_status != "Pending":

            mysql.connection.rollback()

            return redirect(
                url_for("admin_dashboard")
            )


        cursor.execute("""
            UPDATE businesses
            SET
                approval_status = 'Approved',
                rejection_reason = NULL
            WHERE id = %s
              AND approval_status = 'Pending'
        """, (
            business_id,
        ))


        cursor.execute("""
            INSERT INTO business_verification_audit
            (
                business_id,
                admin_user_id,
                old_status,
                new_status,
                rejection_reason
            )
            VALUES
            (
                %s,
                %s,
                %s,
                'Approved',
                NULL
            )
        """, (
            business_id,
            admin_user_id,
            current_status
        ))


        create_notification(
            business_user_id,
            "business_approved",
            "Business Approved",
            (
                f"Your business \"{business_name}\" "
                f"has been approved and your RentEZ "
                f"business account is now active."
            ),
            url_for(
                "business_dashboard"
            )
        )


        mysql.connection.commit()


    except Exception as e:

        mysql.connection.rollback()

        print(
            "Business approval failed:",
            e
        )

        return "Unable to approve business.", 500

    finally:

        cursor.close()


    send_email(
        business_email,
        "Your RentEZ Business Has Been Approved",
        f"""Hello,

Your business "{business_name}" has been approved
on RentEZ.

Your business account is now active.

You can now log in to your Business Portal and
start managing your equipment and bookings.

Welcome to RentEZ!
"""
    )


    return redirect(
        url_for("admin_dashboard")
    )


# =========================================================
# REJECT BUSINESS
# =========================================================
@app.route(
    "/admin/business/<int:business_id>/reject",
    methods=["POST"]
)
def reject_business(business_id):

    if not admin_logged_in():

        return redirect(
            url_for("admin_login")
        )


    reason = request.form.get(
        "rejection_reason",
        ""
    ).strip()


    if not reason:

        return redirect(
            url_for("admin_dashboard")
        )


    reason = reason[:2000]

    admin_user_id = session["user_id"]

    cursor = mysql.connection.cursor()

    try:

        cursor.execute("""
            SELECT
                id,
                business_name,
                business_email,
                user_id,
                approval_status
            FROM businesses
            WHERE id = %s
            FOR UPDATE
        """, (
            business_id,
        ))

        business = cursor.fetchone()


        if not business:

            mysql.connection.rollback()

            return "Business not found.", 404


        business_name = business[1]
        business_email = business[2]
        business_user_id = business[3]
        current_status = business[4]


        if current_status != "Pending":

            mysql.connection.rollback()

            return redirect(
                url_for("admin_dashboard")
            )


        cursor.execute("""
            UPDATE businesses
            SET
                approval_status = 'Rejected',
                rejection_reason = %s
            WHERE id = %s
              AND approval_status = 'Pending'
        """, (
            reason,
            business_id
        ))


        cursor.execute("""
            INSERT INTO business_verification_audit
            (
                business_id,
                admin_user_id,
                old_status,
                new_status,
                rejection_reason
            )
            VALUES
            (
                %s,
                %s,
                %s,
                'Rejected',
                %s
            )
        """, (
            business_id,
            admin_user_id,
            current_status,
            reason
        ))


        create_notification(
            business_user_id,
            "business_rejected",
            "Business Verification Update",
            (
                f"Your business application was "
                f"rejected. Reason: {reason}"
            ),
            url_for(
                "business_profile"
            )
        )


        mysql.connection.commit()


    except Exception as e:

        mysql.connection.rollback()

        print(
            "Business rejection failed:",
            e
        )

        return "Unable to reject business.", 500

    finally:

        cursor.close()


    send_email(
        business_email,
        "RentEZ Business Verification Update",
        f"""Hello,

Your business "{business_name}" was not approved
for RentEZ at this time.

Reason:

{reason}

Please review your submitted information and
contact RentEZ support if you need assistance.
"""
    )


    return redirect(
        url_for("admin_dashboard")
    )
    
    
    
@app.route("/admin/business/document/<int:document_id>")
def admin_business_document(document_id):

    # =====================================================
    # ADMIN AUTHENTICATION
    # =====================================================

    if not admin_logged_in():
        return redirect(url_for("admin_login"))


    cursor = mysql.connection.cursor()

    try:

        # =================================================
        # GET DOCUMENT FROM DATABASE
        # =================================================

        cursor.execute("""
            SELECT
                business_id,
                document_path
            FROM business_documents
            WHERE id = %s
        """, (
            document_id,
        ))

        document = cursor.fetchone()

    finally:
        cursor.close()


    # =====================================================
    # DOCUMENT NOT FOUND
    # =====================================================

    if not document:
        return "Document not found.", 404


    business_id = document[0]
    document_path = document[1]


    # =====================================================
    # EXTRA SAFETY CHECK
    # =====================================================

    # The database should contain paths such as:
    # uploads/business_documents/<generated filename>

    expected_prefix = "uploads/business_documents/"

    if not document_path.startswith(expected_prefix):
        return "Invalid document path.", 404


    # Only allow the filename that exists inside our
    # dedicated business-document directory.

    filename = os.path.basename(document_path)

    if not filename:
        return "Document not found.", 404


    # Make absolutely sure the resolved path remains inside
    # BUSINESS_DOCUMENT_FOLDER.

    requested_path = os.path.abspath(
        os.path.join(
            BUSINESS_DOCUMENT_FOLDER,
            filename
        )
    )

    allowed_folder = os.path.abspath(
        BUSINESS_DOCUMENT_FOLDER
    )

    if not requested_path.startswith(
        allowed_folder + os.sep
    ):
        return "Invalid document path.", 403


    # =====================================================
    # FILE MUST EXIST
    # =====================================================

    if not os.path.isfile(requested_path):
        return "Document file not found.", 404


    # =====================================================
    # SERVE DOCUMENT
    # =====================================================

    return send_from_directory(
        BUSINESS_DOCUMENT_FOLDER,
        filename,
        as_attachment=False
    )
    
    
# =========================================================
# ADMIN BUSINESS DETAIL
# =========================================================
@app.route("/admin/business/<int:business_id>")
def admin_business_detail(business_id):

    if not admin_logged_in():
        return redirect(url_for("admin_login"))

    cursor = mysql.connection.cursor()

    try:

        # =====================================================
        # BUSINESS
        # =====================================================

        cursor.execute("""
            SELECT
                b.id,
                b.business_name,
                b.business_email,
                b.business_phone,
                b.registration_number,
                b.address,
                b.city,
                b.description,
                b.approval_status,
                b.rejection_reason,
                b.created_at
            FROM businesses b
            WHERE b.id = %s
        """, (
            business_id,
        ))

        business_row = cursor.fetchone()

        if not business_row:
            return "Business not found.", 404

        business = {
            "id": business_row[0],
            "name": business_row[1],
            "email": business_row[2],
            "phone": business_row[3],
            "registration_number": business_row[4],
            "address": business_row[5],
            "city": business_row[6],
            "description": business_row[7],
            "status": business_row[8],
            "rejection_reason": business_row[9],
            "created_at": business_row[10]
        }


        # =====================================================
        # DOCUMENTS
        # =====================================================

        cursor.execute("""
            SELECT
                id,
                document_type,
                document_path,
                uploaded_at
            FROM business_documents
            WHERE business_id = %s
            ORDER BY uploaded_at DESC
        """, (
            business_id,
        ))

        document_rows = cursor.fetchall()

        documents = [
            {
                "id": row[0],
                "type": row[1],
                "path": row[2],
                "uploaded_at": row[3]
            }
            for row in document_rows
        ]


        # =====================================================
        # EQUIPMENT
        # =====================================================

        cursor.execute("""
            SELECT
                id,
                name,
                category,
                description,
                price_per_day,
                total_quantity,
                available_quantity,
                available,
                is_active,
                created_at
            FROM equipment
            WHERE business_id = %s
            ORDER BY created_at DESC
        """, (
            business_id,
        ))

        equipment_rows = cursor.fetchall()

        equipment = [
            {
                "id": row[0],
                "name": row[1],
                "category": row[2],
                "description": row[3],
                "price_per_day": row[4],
                "total_quantity": row[5],
                "available_quantity": row[6],
                "available": row[7],
                "is_active": row[8],
                "created_at": row[9]
            }
            for row in equipment_rows
        ]


        # =====================================================
        # BOOKINGS
        # =====================================================

        cursor.execute("""
            SELECT
                bk.id,
                bk.start_date,
                bk.end_date,
                bk.quantity,
                bk.daily_rate,
                bk.total_amount,
                bk.booking_status,
                bk.payment_status,
                e.name,
                u.full_name,
                u.email
            FROM bookings bk
            JOIN equipment e
                ON bk.equipment_id = e.id
            JOIN users u
                ON bk.user_id = u.id
            WHERE e.business_id = %s
            ORDER BY bk.start_date DESC, bk.id DESC
        """, (
            business_id,
        ))

        booking_rows = cursor.fetchall()

        bookings = [
            {
                "id": row[0],
                "start_date": row[1],
                "end_date": row[2],
                "quantity": row[3],
                "daily_rate": row[4],
                "total_amount": row[5],
                "booking_status": row[6],
                "payment_status": row[7],
                "equipment_name": row[8],
                "customer_name": row[9],
                "customer_email": row[10]
            }
            for row in booking_rows
        ]


        # =====================================================
        # VERIFICATION HISTORY
        # =====================================================

        cursor.execute("""
            SELECT
                a.id,
                a.old_status,
                a.new_status,
                a.rejection_reason,
                a.created_at,
                u.full_name,
                u.email
            FROM business_verification_audit a
            JOIN users u
                ON a.admin_user_id = u.id
            WHERE a.business_id = %s
            ORDER BY a.created_at DESC
        """, (
            business_id,
        ))

        audit_rows = cursor.fetchall()

        audit_history = [
            {
                "id": row[0],
                "old_status": row[1],
                "new_status": row[2],
                "reason": row[3],
                "created_at": row[4],
                "admin_name": row[5],
                "admin_email": row[6]
            }
            for row in audit_rows
        ]


        # =====================================================
        # SUMMARY COUNTS
        # =====================================================

        equipment_count = len(equipment)

        active_equipment_count = sum(
            1
            for item in equipment
            if item["is_active"]
        )

        booking_count = len(bookings)

        paid_booking_count = sum(
            1
            for booking in bookings
            if booking["payment_status"] == "Paid"
        )


        return render_template(
            "admin_business_detail.html",

            business=business,
            documents=documents,
            equipment=equipment,
            bookings=bookings,
            audit_history=audit_history,

            equipment_count=equipment_count,
            active_equipment_count=active_equipment_count,
            booking_count=booking_count,
            paid_booking_count=paid_booking_count
        )

    finally:
        cursor.close()


@app.route('/business/add-equipment', methods=['GET', 'POST'])
def add_equipment():

    # Business must be logged in
    if (
        "user_id" not in session
        or session.get("user_type") != "Business"
        or "business_id" not in session
    ):
        return redirect(url_for("business_login"))

    business_id = session['business_id']

    cursor = mysql.connection.cursor()

    # Verify business is still approved
    cursor.execute("""
        SELECT approval_status
        FROM businesses
        WHERE id = %s
    """, (business_id,))

    business = cursor.fetchone()

    if not business or business[0] != 'Approved':

        cursor.close()

        return redirect(url_for('business_login'))

    # =========================
    # SHOW FORM
    # =========================

    if request.method == 'GET':

        cursor.close()

        return render_template(
            'business_add_equipment.html'
        )

    # =========================
    # GET FORM DATA
    # =========================

    name = request.form.get('name', '').strip()
    category = request.form.get('category', '').strip()
    description = request.form.get('description', '').strip()
    price_per_day = request.form.get('price_per_day', '').strip()

    # NEW: quantity
    total_quantity = request.form.get(
        'total_quantity',
        '1'
    ).strip()

    image = request.files.get('image')

    # =================================================
    # RENTAL AVAILABILITY
    # =================================================

    is_available_for_rental = (
        request.form.get("available") == "1"
    )

    available = (
        1
        if is_available_for_rental
        else 0
    )

    is_active = available

    # =========================
    # BASIC VALIDATION
    # =========================

    if (
        not name
        or not category
        or not price_per_day
        or not total_quantity
        or not image
    ):

        cursor.close()

        return render_template(
            'business_add_equipment.html',
            error='Please complete all required fields.'
        )

    # =========================
    # VALIDATE PRICE
    # =========================

    try:

        price_per_day = float(price_per_day)

    except ValueError:

        cursor.close()

        return render_template(
            'business_add_equipment.html',
            error='Please enter a valid rental price.'
        )

    if price_per_day <= 0:

        cursor.close()

        return render_template(
            'business_add_equipment.html',
            error='Rental price must be greater than zero.'
        )

    # =========================
    # VALIDATE QUANTITY
    # =========================

    try:

        total_quantity = int(total_quantity)

    except ValueError:

        cursor.close()

        return render_template(
            'business_add_equipment.html',
            error='Quantity must be a whole number.'
        )

    if total_quantity < 1:

        cursor.close()

        return render_template(
            'business_add_equipment.html',
            error='Quantity must be at least 1.'
        )

    # =========================
    # IMAGE VALIDATION
    # =========================

    filename = secure_filename(
        image.filename
    )

    if not filename:

        cursor.close()

        return render_template(
            'business_add_equipment.html',
            error='Please select a valid image.'
        )

    extension = get_file_extension(filename)

    if extension not in ALLOWED_EQUIPMENT_IMAGES:

        cursor.close()

        return render_template(
            'business_add_equipment.html',
            error=(
                "Only JPG, JPEG, PNG and WEBP images are allowed."
            )
        )

    # Check file size
    image.stream.seek(0, os.SEEK_END)
    image_size = image.stream.tell()
    image.stream.seek(0)

    if image_size > MAX_EQUIPMENT_IMAGE_SIZE:

        cursor.close()

        return render_template(
            'business_add_equipment.html',
            error="Equipment image must be 5 MB or smaller."
        )

    # Check actual file contents
    if not valid_file_signature(image, extension):

        cursor.close()

        return render_template(
            'business_add_equipment.html',
            error=(
                "The uploaded file does not appear to be "
                "a valid image."
            )
        )

    # Generate a unique server-side filename
    unique_filename = (
        f"equipment_{business_id}_"
        f"{uuid.uuid4().hex}.{extension}"
    )

    image_path = os.path.join(
        EQUIPMENT_UPLOAD_FOLDER,
        unique_filename
    )

    image.save(image_path)

    # =========================
    # SAVE EQUIPMENT
    # =========================

    cursor.execute("""
        INSERT INTO equipment (
            business_id,
            name,
            category,
            description,
            price_per_day,
            image,
            available,
            total_quantity,
            available_quantity,
            is_active
        )
        VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s
        )
    """, (
        business_id,
        name,
        category,
        description,
        price_per_day,
        unique_filename,
        available,
        total_quantity,
        total_quantity,
        is_active
    ))

    mysql.connection.commit()

    cursor.close()

    flash(
        f'"{name}" was added successfully.',
        "success"
    )

    return redirect(
        url_for("business_equipment")
    )


@app.route("/terms")
def terms_conditions():

    return render_template(
        "terms_conditions.html"
    )
# =========================================================
# PUBLIC INFORMATION PAGES
# =========================================================

@app.route("/about")
def about():
    return render_template(
        "about.html"
    )


@app.route("/faq")
def faq():
    return render_template(
        "faq.html"
    )


@app.route(
    "/contact",
    methods=["GET", "POST"]
)
def contact():

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        sender_email = request.form.get(
            "email",
            ""
        ).strip()

        topic = request.form.get(
            "topic",
            ""
        ).strip()

        message = request.form.get(
            "message",
            ""
        ).strip()


        if not all([
            name,
            sender_email,
            topic,
            message
        ]):

            return render_template(
                "contact.html",
                contact_error=(
                    "Please fill in all fields before sending your message."
                )
            )


        email_body = f"""
New message received through the RentEZ Contact Form

Name:
{name}

Email:
{sender_email}

Topic:
{topic}

Message:
{message}

--------------------------------
RentEZ Contact Form
"""


        sent = send_email(
            CONTACT_EMAIL,
            f"RentEZ Contact Form - {topic.title()}",
            email_body
        )


        if sent:

            return render_template(
                "contact.html",
                contact_success=(
                    "Your message has been sent successfully. "
                    "The RentEZ admin will get back to you soon."
                )
            )


        return render_template(
            "contact.html",
            contact_error=(
                "Unable to send your message right now. "
                "Please try again later."
            )
        )


    return render_template(
        "contact.html"
    )


@app.route("/privacy")
def privacy():
    return render_template(
        "privacy.html"
    )
    

@app.route("/info")
def site_info():

    return render_template(
        "site_info.html"
    )


if __name__ == "__main__":

    app.run(
        debug=os.getenv(
            "FLASK_DEBUG",
            "false"
        ).lower() == "true"
    )