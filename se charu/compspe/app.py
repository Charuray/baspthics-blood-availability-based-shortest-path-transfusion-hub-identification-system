from flask import Flask, render_template, request
from flask import Flask, session, jsonify
from flask_session import Session
import pyodbc
import requests
from flask import request, jsonify
from datetime import datetime
from decimal import Decimal
import uuid

app = Flask(__name__)
app.secret_key = 'mysecretkey'

SESSION_API_URL = "http://127.0.0.1:5000/get_user_role"

def get_db_connection():
    return pyodbc.connect('DSN=ODBC_2005;UID=pingipengi;PWD=pp', autocommit=True)

@app.route('/get_user_role', methods=['GET'])
def get_user_role():
    try:
        response = requests.get(SESSION_API_URL)
        if response.status_code == 200:
            role = response.json().get("role")
            session['role'] = role
            return jsonify({"role": role}), 200
        else:
            return jsonify({"error": "Unable to fetch admin role."}), 400
    except Exception as e:
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500
@app.route('/antibody_screen', methods=['GET','POST'])
def antibody_screen():
    return render_template("antibody_screen.html")

@app.route('/serologic_testing',methods=['GET','POST'])
def serologic_testing():
    results=[]
    conn=get_db_connection()
    if conn:
        cursor=conn.cursor()

    query='''SELECT B.PID, B.BBID, B.BLOOD_GROUP, B.UNITS, B.R_STATUS FROM BB_REQUESTS B  WHERE B.R_STATUS='Approved for Crossmatch' 
    AND B.PID IN (SELECT PATIENT_ID FROM HOSP_REQUESTS WHERE STATUS='Need Serologic Test' )'''
    params=[]

    
    if request.method == 'POST':
        patient_id=request.form.get('pid') or ""
        print("Patient ID: ",patient_id)

        if patient_id != "PA-":
            query+=" AND B.PID = ?"
            params.append(patient_id)
        
    cursor.execute(query,params)
    print("Query executed : ", query, " with params ", params)

    results=cursor.fetchall()
    cursor.close()
    return render_template("serologic_testing.html", results=results)

@app.route('/check_exm', methods=['GET','POST'])
def check_exm():
    results=[]
    conn=get_db_connection()
    if conn:
        cursor=conn.cursor()

    query='''SELECT H.PATIENT_ID, AB.REACTION_IS, AB.REACTION_37C, AB.REACTION_AHG, AB.RESULT, AB.INTERPRETATION
        FROM HOSP_REQUESTS H JOIN ABSCREEN AB ON H.PATIENT_ID = AB.PID '''
    params=[]

    
    if request.method == 'POST':
        patient_id=request.form.get('pid') or ""
        print("Patient ID: ",patient_id)

        if patient_id != "PA-":
            query+=" WHERE AB.PID = ?"
            params.append(patient_id)
        
    cursor.execute(query,params)
    print("Query executed : ", query, " with params ", params)

    results=cursor.fetchall()
    cursor.close()

    return render_template("check_exm.html", results=results)

@app.route('/change_request_status', methods=['POST'])
def change_request_status():
    data = request.get_json()

    patient_id = data.get('patient_id')
    blood_bank_id = int(data.get('blood_bank_id'))
    group=data.get('group')
    units = int(data.get('units'))
    new_status = data.get('new_status')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
         
        query ="""
            UPDATE bb_requests 
            SET r_status = ?
            WHERE pid = ? AND bbid = ? AND units = ? AND blood_group = ? 
        """
        params=(new_status, patient_id, blood_bank_id, units, group)
        cursor.execute(query, params)
        print("Status change query executed.")
        conn.commit()

        if new_status=="Approved":
            cursor.execute("""
                           UPDATE HOSP_REQUESTS SET STATUS='Approved' WHERE PATIENT_ID=?""",
                           (patient_id))

        if new_status=="Approved":
            cursor.execute("""
                           UPDATE BLOOD_BANK_LIST SET UNITS = UNITS - ? WHERE BID =? AND B_GROUP = ?""",
                           (units,blood_bank_id,group))
            cursor.commit()
        return jsonify({"success": True, "message": "Status updated successfully!"})
    except Exception as e:
        conn.rollback()
        print("Error updating status:", e)
        return jsonify({"success": False, "message": "Failed to update status."})

@app.route('/submit_screening', methods=['POST'])
def submit_screening():
    conn = get_db_connection()
    cursor = conn.cursor()
    screening_data = request.get_json()

    pid=screening_data['pid']
    ap=screening_data['antigen_profile']

    query="SELECT PID FROM PATIENT WHERE PID= ?"
    params=[pid]

    cursor.execute(query,params)
    patient=cursor.fetchone()
    if patient:
        patient=patient[0]
    if not patient:
        status = "error"
        message = "The patient is not registered."
        return jsonify({"status": status, "message": message})
    
    query="SELECT PID FROM ABSCREEN WHERE PID= ? AND ANTIGEN_PROFILE = ?"
    params=[pid,ap]

    cursor.execute(query,params)
    patient=cursor.fetchone()
    if patient:
        status = "error"
        message = "The patient's screening details with this antigen profile have already been registered."
        return jsonify({"status": status, "message": message})

    # Parse and clean input
    screen_date_str = screening_data.get('screen_date')
    if screen_date_str:
        screening_data['screen_date'] = datetime.strptime(screen_date_str, "%Y-%m-%d").date()
    else:
        screening_data['screen_date'] = datetime.now().date()

    # Assign a unique Reaction ID (RID)
    # You can use UUID or any generator — here we'll do a simple manual ID for example
    screening_data['rid'] = f"RID-{uuid.uuid4().hex[:8].upper()}"

    # Handle missing/optional fields gracefully
    screening_data['interpretation'] = screening_data.get('interpretation') or ""
    screening_data['antigen_profile'] = screening_data.get('antigen_profile') or ""

    # Prepare INSERT query
    query = '''
        INSERT INTO ABSCREEN (
            REACTION_ID, PID, SCREEN_DATE, CELL_PANEL, ANTIGEN_PROFILE,
            REACTION_IS, REACTION_37C, REACTION_AHG,
            RESULT, INTERPRETATION
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    '''

    params = [
        screening_data['rid'],
        screening_data['pid'],
        screening_data['screen_date'],
        screening_data['cell_panel'],
        screening_data['antigen_profile'],
        screening_data['reaction_is'],
        screening_data['reaction_37c'],
        screening_data['reaction_ahg'],
        screening_data['screening_result'],
        screening_data['interpretation']
    ]

    print("Query:", query)
    print("Params:", params)

    try:
        cursor.execute(query, params)
        conn.commit()
        status = "success"
        message = "Antibody Screening data inserted successfully!"
    except Exception as e:
        conn.rollback()
        status = "error"
        message = str(e)
    finally:
        conn.close()

    return jsonify({"status": status, "message": message})

if __name__ == '__main__':
    app.run(port=5007, debug=True)