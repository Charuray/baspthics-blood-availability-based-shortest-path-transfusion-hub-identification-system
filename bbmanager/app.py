from flask import Flask, render_template, request
from flask import Flask, session, jsonify
from flask_session import Session
import redis
import pyodbc
import requests
import pywhatkit as kit

app = Flask(__name__)
app.secret_key = 'mysecretkey'

SESSION_API_URL = "http://127.0.0.1:5000/get_user_role"
@app.route('/check_session')
def check_session():
    if 'user_id' in session:
        return jsonify({"user_id": session["user_id"], "role": session["role"]})
    return jsonify({"error": "Session expired"}), 401

def get_db_connection():
    return pyodbc.connect('DSN=oracle;UID=system;PWD=0608', autocommit=True)

def send_approval_message(phone_number, pid):
    try:
        formatted_phone = phone_number.strip()

        # Step 1: Compose the blood stock summary message
        message = "🩸 *Blood bank management* 🩸\n\n Your status has been approved!"
        message += "\nStay healthy, stay safe!\n- Blood Bank Team"

        
        # Send stock summary message
        kit.sendwhatmsg_instantly(
            phone_no=formatted_phone,
            message=message,
            wait_time=15
        )
        print(f"✅ Blood stock summary")
        
        conn=get_db_connection()
        cursor=conn.cursor()
        
        query="DELETE FROM BB_REQUESTS WHERE PID=?"
        params=[pid]

        cursor.execute(query,params)
        print("Query executed: ", query, " with params: ", params)

        query="DELETE FROM HOSP_REQUESTS WHERE PATIENT_ID=?"
        params=[pid]

        cursor.execute(query,params)
        print("Query executed: ", query, " with params: ", params)
    except Exception as e:
        print(f"❌ Error after approval: {e}")

def send_approval_message(phone_number, pid):
    try:
        formatted_phone = phone_number.strip()

        # Step 1: Compose the blood stock summary message
        message = "🩸 *Blood bank management* 🩸\n\n Your status has been approved!"
        message += "\nStay healthy, stay safe!\n- Blood Bank Team"

        
        # Send stock summary message
        kit.sendwhatmsg_instantly(
            phone_no=formatted_phone,
            message=message,
            wait_time=15
        )
        print(f"✅ Blood stock summary")
        
        conn=get_db_connection()
        cursor=conn.cursor()
        
        query="DELETE FROM BB_REQUESTS WHERE PID=?"
        params=[pid]

        cursor.execute(query,params)
        print("Query executed: ", query, " with params: ", params)

        query="DELETE FROM HOSP_REQUESTS WHERE PATIENT_ID=?"
        params=[pid]

        cursor.execute(query,params)
        print("Query executed: ", query, " with params: ", params)
    except Exception as e:
        print(f"❌ Error after approval: {e}")

def send_status_message(phone_number):
    try:
        formatted_phone = phone_number.strip()

        # Step 1: Compose the blood stock summary message
        message = "🩸 *Blood bank management* 🩸\n\n Your request is undergoing serologic crossmatch!\n\nPlease be patient until you get your crossmatch result!"
        message += "\nStay healthy, stay safe!\n- Blood Bank Team"

        
        # Send stock summary message
        kit.sendwhatmsg_instantly(
            phone_no=formatted_phone,
            message=message,
            wait_time=15
        )
        print(f"✅ Message to patient sent!")
        
        
    except Exception as e:
        print(f"❌ Error after approval: {e}")

@app.route('/manage_inventory', methods=['GET', 'POST'])
def manage_inventory():
    try:
        results = []
        locations = []

        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()

        # Handle form submission
        if request.method == 'POST':
            group = request.form.get('Compatibility', '')
            blood="A"+group
            user_id = request.form.get('user_id', '')

            if user_id:
                user_id = user_id[3:]  # Removing 'HO-' prefix if needed
                user_id = int(user_id)
                print("New user ID:", user_id)

            query="SELECT BID, BNAME, B_GROUP, UNITS FROM blood_bank_list WHERE BID= ? "
            params=[user_id]
            
            if group:
                query+="AND INSTR(COMPATIBILITY,?)!=0 AND REGEXP_COUNT(COMPATIBILITY,?)!=REGEXP_COUNT(COMPATIBILITY,?)"
                params.append(group)
                params.append(blood)
                params.append(group)

            cursor.execute(query,params)
            print("Query executed: ", query, "\nParams: ", params)
            results = cursor.fetchall()

            cursor.close()
        return render_template("manage_inventory.html", results=results, locations=locations)


    except Exception as e:
        return jsonify({"error": str(e)}), 500  # Return error message if failure


@app.route('/approve_requests',methods=['GET','POST'])
def approve_requests():
    results = []
    locations = []
    
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor()

        # Handle form submission
        if request.method == 'POST':
            blood_type = request.form.get('blood_type', '')
            user_id = request.form.get('user_id', '')

            if user_id:
                user_id = user_id[3:]  # Removing 'HO-' prefix if needed
                user_id = int(user_id)
                print("New user ID:", user_id)

            query = """ 
            SELECT REQUESTID, BBID, BLOOD_GROUP, UNITS, REQUEST_DATE, LOCATION 
            FROM BB_REQUESTS WHERE R_STATUS = 'Pending' AND BBID= ?
            """
            params = [user_id]

            if blood_type:
                query += " AND BLOOD_GROUP = ?"
                params.append(blood_type)

            print("Executing query:", query)
            print("With parameters:", params)

            cursor.execute(query, params)
            results = cursor.fetchall()

        cursor.close()
        connection.close()

    return render_template("approve_requests.html", results=results, locations=locations, user_id=session.get('user_id'))

@app.route('/update_request_status',methods=['POST'])
def update_request_status():
    data=request.get_json()
    request_id = data.get('request_id', '')
    new_status = data.get('status', '')
    print("Request ID: " + request_id + " new Status: " + new_status)
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor()

        query = "SELECT PID FROM BB_REQUESTS WHERE REQUESTID =?"
        params = [request_id]
        cursor.execute(query, params)
        pid=cursor.fetchone()
        pid=pid[0]

        query=("""SELECT PHNO FROM PATIENT WHERE PID=?""" )
        params=[pid]
        cursor.execute(query,params)
        print("Query: ", query, "Params: ", params)
        phno=cursor.fetchone()
        phno=phno[0]
        
        query = "UPDATE BB_REQUESTS SET R_STATUS =? WHERE REQUESTID =?"
        params = [new_status, request_id]
        cursor.execute(query, params)
        print("query executed: ", query ,"\nwith params: ", params)

        query = "SELECT PID FROM BB_REQUESTS WHERE REQUESTID=?"
        params = [request_id]
        cursor.execute(query, params)
        print("query executed: ", query ,"\nwith params: ", params)

        result=cursor.fetchone()
        result=result[0]

        if result:
            query = "SELECT STATUS FROM HOSP_REQUESTS WHERE PATIENT_ID=?"
            params = [result]
            cursor.execute(query, params)
            print("query executed: ", query ,"\nwith params: ", params)

            result=cursor.fetchone()
            result=result[0]

            if result=="Need Serologic Test":
                send_status_message(phno)
                print("Serologic whatsapp message task generation started.")
        else:
            send_approval_message()
                


        
        cursor.close()
        connection.commit()
        connection.close()
        return jsonify({"success": True})
    return jsonify({"error": "Failed to update request status."}), 500

if __name__ == '__main__':
    app.run(port=5002, debug=True)


