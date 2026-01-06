from flask import Flask, request, render_template, redirect, url_for, session, flash, jsonify, get_flashed_messages
import pyodbc
import datetime
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
import random
from flask_bcrypt import bcrypt
from decimal import Decimal
from apscheduler.schedulers.background import BackgroundScheduler
import pywhatkit as kit
import requests

app = Flask(__name__)
app.secret_key='mysecretkey'

#bcrypt = Bcrypt(app)

SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
SENDER_EMAIL = '*******'  # Update with your email
SENDER_PASSWORD = '******'  # App-specific password
SESSION_API_URL = "http://127.0.0.1:5000/get_user_role"

role_id = None


def start_low_stock_task():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_and_send_weekly_blood_stock, 'interval', minutes=1) 
    scheduler.start()
    print("Background scheduler started.")

    
@app.route('/get_user_role', methods=['GET'])
def get_user_role():

    if not role_id:
        return jsonify({"error": "Not logged in"}), 401  # Unauthorized access
    print("ROLE ID____________:", role_id)
    return jsonify({"role": role_id}), 200




def send_blood_stock_update(phone_number, blood_stock_dict):
    try:
        formatted_phone = phone_number.strip()

        # Step 1: Compose the blood stock summary message
        message = "🩸 *Blood Stock Update -  Blood Bank* 🩸\n\n"
        message += "Here’s the current availability:\n\n"

        for group, units in blood_stock_dict.items():
            message += f"🔹 {group}: {units} unit(s)\n"

        message += "\nStay healthy, stay safe!\n- Blood Bank Team"

        low_stock = [f"{group} ({units} unit{'s' if units != 1 else ''})"
                     for group, units in blood_stock_dict.items() if units < 5]
        
        if low_stock:
            alert_message = "⚠️ *Low Blood Stock Alert!* ⚠️\n\n"
            alert_message += "The following blood groups are running low:\n\n"
            alert_message += "\n".join(f"🔻 {item}" for item in low_stock)
            alert_message += "\n\nPlease consider scheduling donations.\nThank you!"

        message+=alert_message
        # Send stock summary message
        kit.sendwhatmsg_instantly(
            phone_no=formatted_phone,
            message=message,
            wait_time=15
        )
        print(f"✅ Blood stock summary")

    except Exception as e:
        print(f"❌ WhatsApp message error: {e}")

def check_and_send_weekly_blood_stock():
    conn = get_db_connection()
    cursor = conn.cursor()
    today = datetime.now().date()
    print("Today's date: ", today)

    user_id = session.get('user_id')
    if not user_id:
        print("No user_id found in session.")
        return

    print("Current user id: ", user_id)

    # Fetch phone number (unpack from tuple)
    cursor.execute("SELECT PHONE FROM USER_ROLE WHERE USER_ID = ?", (user_id,))
    result = cursor.fetchone()
    if not result:
        print("No phone number found for user.")
        return
    phone_number = result[0]

    # Fetch last sent date (handle properly)
    cursor.execute("SELECT LastSent FROM Stock_Notification_Log WHERE PhoneNumber = ?", (phone_number,))
    last_sent = cursor.fetchone()
    last_sent_date = last_sent[0].date() if last_sent and last_sent[0] else None

    print("Last sent date: ", last_sent_date)

    if not last_sent_date or (today - last_sent_date).days >= 7:
        bb_id = user_id[3:]  # assuming BBxxx format
        print("Blood bank ID: ", bb_id)

        # Fetch current blood stock
        cursor.execute("SELECT B_GROUP, Units FROM BLOOD_BANK_LIST WHERE BID = ?", (bb_id,))
        rows = cursor.fetchall()
        blood_stock_dict = {row[0]: row[1] for row in rows}
        print("Fetched blood group values:\n", blood_stock_dict)
        phone_number="+91"+str(phone_number)
        # Send update
        send_blood_stock_update(phone_number, blood_stock_dict)

        # Convert date to string (Oracle compatibility)
        today_str = today.strftime('%Y-%m-%d')

        # Update or insert log using raw SQL to avoid ODBC issues
        if last_sent:
            query = f"""
                UPDATE Stock_Notification_Log 
                SET LastSent = TO_DATE('{today_str}', 'YYYY-MM-DD') 
                WHERE PhoneNumber = '{phone_number}'
            """
        else:
            query = f"""
                INSERT INTO Stock_Notification_Log (PhoneNumber, LastSent)
                VALUES ('{phone_number}', TO_DATE('{today_str}', 'YYYY-MM-DD'))
            """
        cursor.execute(query)
        conn.commit()

    cursor.close()





# 🔹 Database Connection Function
def get_db_connection():
    return pyodbc.connect('DSN=oracle;UID=system;PWD=0608', autocommit=True)

# 🔹 Generate Unique User ID Based on Role
def generate_user_id(role):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM user_role WHERE role = ?", (role,))
    count = cursor.fetchone()[0]  # Fetch the count

    if count is None:
        count = 1001  # If no users exist, start from 1
    else:
        count = int(count) + 1  # 🔹 Ensure count is an integer before using it

    prefix = role[:2].upper()  # Example: 'HO' for Hospital
    new_id = f"{prefix}-{count:04d}"  # Format: Role + 4-digit counter

    conn.close()
    return new_id


# 🔹 Index Route
@app.route('/', methods=["GET", "POST"])
def mobile_table():
    flash_messages = {category: message for category, message in get_flashed_messages(with_categories=True)}
    return render_template('login.html', flash_messages=flash_messages)

# 🔹 User Registration
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        role = request.form["role"]
        name = request.form["name"]
        phone = request.form["phone"]
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for("register"))
        user_id = generate_user_id(role)

        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO user_role (user_id, role, name, phone, email, password) VALUES (?, ?, ?, ?, ?, ?)",
                    (user_id, role, name, phone, email, password),
                )
                conn.commit()

            return redirect(url_for("success", user_id=user_id))
        except Exception as e:
            print(e)
            flash(f"Error: {e}", "danger")

    return render_template("register.html")

@app.route('/forgot_password',methods=['GET','POST'])
def forgot_password():
    flash_messages = {category: message for category, message in get_flashed_messages(with_categories=True)}
    return render_template('forgot_password.html', flash_messages=flash_messages)



@app.route('/change_password', methods=['GET','POST'])
def change_password():

    try:
        if request.method == 'POST':
            data = request.get_json()
            username_or_email = data.get('usernameOrEmail')
            current_password = data.get('currentPassword')
            new_password = data.get('newPassword')
            confirm_new_password = data.get('confirmNewPassword')
            forgot = data.get('forgot')

            connection = get_db_connection()
            cursor = connection.cursor()

            # Check if username or email exists in the database
            cursor.execute("SELECT user_id, email, password FROM user_role WHERE user_id = ? OR email = ?", (username_or_email, username_or_email))
            user_record = cursor.fetchone()
            print(user_record)

            if not user_record:
                return jsonify({"error": "User does not exist."}), 400

            db_password = user_record[2]

            # Verify current password
            if forgot:
                if current_password != db_password:
                    print(current_password,db_password)
                    return jsonify({"error": "Current password is incorrect."}), 400
                
            if len(new_password) < 8 or len(new_password) > 16:
                return jsonify({"error": "Invalid password length."}), 400

            # Verify new password and confirm password match
            if new_password != confirm_new_password:
                return jsonify({"error": "New password and confirm password do not match."}), 400

            # Update the database with the new password
            cursor.execute("""
                UPDATE user_role
                SET prev_password = ?, password = ?
                WHERE user_id = ? OR email = ?
            """, (current_password,new_password, username_or_email, username_or_email))

            connection.commit()

            return jsonify({"success": "Password updated successfully."})

    except pyodbc.Error as e:
            app.logger.error(f"Database error: {str(e)}")
            return jsonify({"error": "Database error occurred."}), 500
    except Exception as e:
            app.logger.error(f"Unexpected error: {str(e)}")
            return jsonify({"error": "An unexpected error occurred."}), 500
    finally:
            if 'cursor' in locals():
                cursor.close()

    return render_template('change_password.html')




otp_sent_time = {}  # To track the OTP resend time for each email

def send_email(recipient, subject, body):
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = SENDER_EMAIL
        msg['To'] = recipient

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        print(f"SMTP Error: {str(e)}")
        return False
    return True


@app.route('/request_otp', methods=['POST'])
def request_otp():
    data = request.json
    email = data.get('email')

    if not email:
        return jsonify({"error": "Email is required."}), 400

    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT user_id FROM user_role WHERE email = ?", (email,))
    user = cursor.fetchone()

    if not user:
        return jsonify({"error": "Email not found in database."}), 404

    # Check OTP resend timer
    now = datetime.now()
    if email in otp_sent_time and now < otp_sent_time[email] + timedelta(minutes=2):
        return jsonify({"error": "OTP resend is unavailable. Please wait 2 minutes."}), 403

    # Generate OTP
    otp = random.randint(100000, 999999)
    print("Generating OTP: ",otp)
    cursor.execute("UPDATE user_role SET otp = ? WHERE email = ?", (otp, email))
    #cursor.execute("SELECT phone FROM users WHERE email = ?", (email,))
    #phone = cursor.fetchone()
    connection.commit()

    # Send OTP via email
    subject = "Your OTP for Password Reset"
    body = f"Your OTP is {otp}. It is valid for 2 minutes."
    if not send_email(email, subject, body):
        return jsonify({"error": "Failed to send OTP, through E-mail. Please try again later."}), 500
    
    otp_sent_time[email] = now  # Update OTP sent time
    return jsonify({"success": "OTP sent successfully.", "otp": otp}), 200


@app.route('/validate_otp', methods=['POST'])
def validate_otp():
    data = request.json
    email = data.get('email')
    otp = data.get('otp')

    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT otp FROM user_role WHERE email = ?", (email,))
        result = cursor.fetchone()

        if not result or int(result[0]) != int(otp):
            return jsonify({"error": "Invalid or expired OTP."}), 400

        return jsonify({"success": "OTP verified successfully."}), 200
    except Exception as e:
        app.logger.error(f"Unexpected error during OTP validation: {str(e)}")
        return jsonify({"error": "An unexpected error occurred."}), 500
    finally:
        cursor.close()

# 🔹 Login Route
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user_id = request.form["username"]
        password = request.form["password"]


        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT user_id, password, role FROM user_role WHERE user_id=?", (user_id,))
                user = cursor.fetchone()

                if user and password == user[1]:
                    session["user_id"] = user[0]
                    print("User ID while logging in: ", user_id, " ", user[0])
                    session["role"] = user[2]
                    global role_id
                    role_id = user[0]
                    flash("Login successful!", "success")
                    print("Session Set:", session.get('user_id'))

                    return redirect(url_for("dashboard"))
                else:
                    flash("Invalid User ID or Password", "danger")
        except Exception as e:
            flash(f"Error: {e}", "danger")

    return render_template("login.html")

# 🔹 Dashboard Route
@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for('login'))
    print(session.get('user_id'),session.get('role'))
    if(session.get('role')=="Blood Bank Manager"):
        check_and_send_weekly_blood_stock()
        print("Whatsapp message generation task started.")
    if(session.get('role')=="Donor"):
        conn=get_db_connection()
        if conn:
            cursor=conn.cursor()
            user_id=session.get('user_id')
            print("User ID: " ,user_id)
            query="SELECT DONORID FROM DONORS WHERE DONORID= ?"
            params=(user_id,)
            cursor.execute(query,params)
            print("Query executed: ", query, " with params ", params)
            result=cursor.fetchone()
            query="SELECT DONOR_ID FROM DONATIONS WHERE DONOR_ID= ?"
            params=(user_id,)
            cursor.execute(query,params)
            print("Query executed: ", query, " with params ", params)
            donor=cursor.fetchone()
            if result and donor:
                return render_template("dashboard.html", username=session.get('user_id'), role=session.get('role'),status="rnd")
            elif result:
                return render_template("dashboard.html", username=session.get('user_id'), role=session.get('role'), status="registered")
            else:
                return render_template("dashboard.html", username=session.get('user_id'), role=session.get('role'), status="notregistered")
    if(session.get('role')=="Patient"):
        conn=get_db_connection()
        if conn:
            cursor=conn.cursor()
            user_id=session.get('user_id')
            print("User ID: " ,user_id)
            query="SELECT PID FROM PATIENT WHERE PID= ?"
            params=(user_id,)
            cursor.execute(query,params)
            print("Query executed: ", query, " with params ", params)
            result=cursor.fetchone()
            if result:
                return render_template("dashboard.html", username=session.get('user_id'), role=session.get('role'),status="registered")
            else:
                return render_template("dashboard.html", username=session.get('user_id'), role=session.get('role'), status="notregistered")
        
    else:
        print("Role: ", session.get('role'))
    return render_template("dashboard.html", username=session.get('user_id'), role=session.get('role'))



@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(port=5000, debug=True)
