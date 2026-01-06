from flask import Flask, request, render_template, redirect, session, jsonify, url_for
import pyodbc
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Needed for session handling

def get_db_connection():
    return pyodbc.connect('DSN=oracle;UID=system;PWD=0608', autocommit=True)

role_id = None

@app.route('/get_user_role', methods=['GET'])
def get_user_role():
    if not role_id:
        return jsonify({"error": "Not logged in"}), 401
    print("ROLE ID____________:", role_id)
    return jsonify({"role": role_id}), 200

@app.route('/enter_donation')
def enter_donation():
    success = request.args.get('success')  # Read the success flag
    return render_template('enter_donation.html', success=success)

@app.route('/submit_donation', methods=['POST'])
def submit_donation():
    donor_id = request.form['donor_id']
    donation_type = request.form['donation_type']
    bb_id = request.form['bb_id']
    blood_group = request.form['blood_group']
    units = request.form['units']
    donated_date = request.form['donated_date'] or datetime.now().strftime('%Y-%m-%d')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO DONATIONS (DONOR_ID, DONATION_TYPE, BB_ID, BLOOD_GROUP, UNITS, DONATED_DATE)
            VALUES (?, ?, ?, ?, ?, TO_DATE(?, 'YYYY-MM-DD'))
        """, (donor_id, donation_type, bb_id, blood_group, units, donated_date))
        conn.commit()
        return redirect(url_for('enter_donation', success='true'))
    except Exception as e:
        return f"Error: {str(e)}"


@app.route('/view_buffer')
def view_donations():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM DONATIONS")
        donations = cursor.fetchall()
        
        # Get column names
        columns = [column[0] for column in cursor.description]
        
        return render_template('view_buffer.html', donations=donations, columns=columns)
    except Exception as e:
        return f"Error fetching donation records: {str(e)}"

if __name__ == '__main__':
    app.run(port=5003, debug=True)
