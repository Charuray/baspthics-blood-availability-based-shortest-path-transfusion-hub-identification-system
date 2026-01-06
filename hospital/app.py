from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import pyodbc
from datetime import datetime
from flask import Flask, session
from flask import Flask, session, jsonify
from flask_session import Session
import redis
import googlemaps
import requests

app = Flask(__name__)
app.secret_key ='mysecretkey'

# API for session-based role retrieval
SESSION_API_URL = "http://127.0.0.1:5000/get_user_role"

API_KEY = "AIzaSyBuUE3VDoS9iZl-o6MqZZ1e-th7CyeYiq8"
gmaps = googlemaps.Client(key=API_KEY)

def get_db_connection():
    return pyodbc.connect('DSN=oracle;UID=system;PWD=0608', autocommit=True)

# Role fetching route (if needed by frontend JS)
@app.route('/get_user_role', methods=['GET'])
def get_user_role():
    try:
        response = requests.get(SESSION_API_URL)
        if response.status_code == 200:
            role = response.json().get("role")
            session['role_id'] = role
            return jsonify({"role": role}), 200
        else:
            return jsonify({"error": "Unable to fetch admin role."}), 400
    except Exception as e:
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500
    
@app.route('/send_user_id', methods=['POST'])
def receive_user_id():
    data = request.get_json()
    user_id = data.get('user_id')

    if user_id:
        print(f"Received user ID: {user_id}")
        return jsonify({"message": "User ID received", "user_id": user_id})
    else:
        return jsonify({"error": "User ID not provided"}), 400
# Route to display blood availability

@app.route('/get_origin', methods=['GET'])
def get_origin():
    connection = get_db_connection()
    if not connection:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        cursor = connection.cursor()
        get_user_role()
        user_id = session['role_id']
        user_id = user_id[3:]  # Extract hospital ID
        
        print(f"Got hospital ID: {user_id}")

        query = '''SELECT latitude, longitude FROM hospital_namelist WHERE hospid = ?'''
        params = [user_id]
        cursor.execute(query, params)
        coord = cursor.fetchone()

        if not coord:
            origin_lat=0
            origin_lng=0
            return jsonify({"error": "Hospital coordinates not found"}), 404
        
        else:
            origin_lat=coord[0]
            origin_lng=coord[1]


        return jsonify({
        'origin_lat': origin_lat,
        'origin_lng': origin_lng
        })

    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return jsonify({"error": "An unexpected error occurred."}), 500

@app.route('/blood_availability', methods=['GET', 'POST'])
def blood_availability():
    results = []  # To store query results
    locations = []  # To store unique locations from DB
    
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor()
    
    pid = request.args.get('patient_id')
    


    query = '''SELECT latitude, longitude FROM hospital_namelist WHERE hospid = ?'''
    get_user_role()
    user_id = session['role_id']
    user_id = user_id[3:]
    params = [user_id]
    cursor.execute(query, params)
    coord = cursor.fetchone()
    blood_type='A+'
    quantity=1
        
    if request.method == 'POST' or pid:
        cursor.execute("SELECT DISTINCT location FROM blood_bank_namelist")
        locations = [row[0] for row in cursor.fetchall()]
        #print(locations)
        pid=request.args.get('patient_id')
        if pid:
            blood_type = request.args.get('blood_type')
            quantity=request.args.get('quantity')
        else:
            blood_type = request.form.get('blood_type', '')
            blood="A"+blood_type
            quantity = request.form.get('quantity', '')
        #rdate = request.form.get('rdate', '')
        #hospital=(13.030947,80.171585)
        query = '''SELECT latitude, longitude FROM hospital_namelist WHERE hospid = ?'''
        get_user_role()
        print("Hospital location: ", coord)
        query = """ 
                SELECT b.b_group, b.units, bb.location, bb.bbid, bb.bbname, BB.LATITUDE, BB.LONGITUDE
                FROM blood_bank_list b
                JOIN blood_bank_namelist bb ON b.bID = bb.bbID 
                WHERE 1=1 
            """
        params = []

            # Add filters based on input
        if blood_type:
                #query+=" AND INSTR(b.COMPATIBILITY,?)!=0 AND REGEXP_COUNT(b.COMPATIBILITY,?)!=REGEXP_COUNT(b.COMPATIBILITY,?)"
                query += " AND b.b_group = :blood_type"
                params.append(blood_type)
                #params.append(blood)
                #params.append(blood_type)
        if quantity:
                query += " AND b.units >= :quantity"
                params.append(int(quantity))

        cursor.execute(query, params)
        print("BLOOD BANK QUERY EXECUTED SUCCESSFULLY")
        results = cursor.fetchall()
        #print(results)

        # Limit to 25 results
        limited_results = results[:25]

        # Extract (latitude, longitude) tuples for each bank
        bank_locations = [(bank[5], bank[6]) for bank in limited_results]

        # Calculate driving distances
        distances = gmaps.distance_matrix(origins=[coord], destinations=bank_locations, mode="driving")


        # **Step 5: Attach distance to each blood bank and sort them**
        # Convert tuple results into dictionaries
        formatted_results = [
            {
                "blood_group": bank[0],
                "units": int(bank[1]),  # Convert Decimal to int
                "location": bank[2],
                "bb_id": int(bank[3]),  # Convert Decimal to int
                "bb_name": bank[4],
                "latitude": float(bank[5]),  # Convert to float
                "longitude": float(bank[6])  # Convert to float
            }
            for bank in limited_results
        ]

        # Fetch distances from Google Maps API
        for i, bank in enumerate(formatted_results):
            distance_text = distances['rows'][0]['elements'][i]['distance']['text']
            distance_value = distances['rows'][0]['elements'][i]['distance']['value']  # in meters
            bank["distance_text"] = distance_text
            bank["distance_value"] = distance_value

        # Sort results by shortest distance
        formatted_results.sort(key=lambda x: x["distance_value"])
        print("Formatted results: ",formatted_results)
        # Render results in the HTML template
        return render_template(
            "blood_availability.html",
            results=formatted_results,
            locations=locations,
            user_id=session.get("user_id"), origin_lat=coord[0], origin_lng=coord[1],
            patient_id=pid,
            blood_type=blood_type,
            quantity=quantity
        )
    return render_template("blood_availability.html", locations=locations, user_id=session.get("user_id"),patient_id=pid, blood_type=blood_type, quantity=quantity)


@app.route('/submit_request', methods=['POST'])
def submit_request():
    conn = get_db_connection()
    get_user_role()
    try:
        
        cursor = conn.cursor()
        data = request.get_json()
        location=data.get('location')
        blood_type = data.get("blood_type")
        quantity = data.get("quantity")  # Might be a string
        request_date = data.get("request_date")  # Already in YYYY-MM-DD
        bloodbankID = data.get("bloodbankID")  # Should be an integer
        patient_id=data.get("patient_id")
        
        print("Patient ID: ", patient_id)
        user_id = session['role_id']  # Expecting string like "HO-123"

        print(f"User ID: {user_id}, Blood Type: {blood_type}, Quantity: {quantity}, BB ID: {bloodbankID}")

        if not all([user_id, blood_type, quantity, request_date, bloodbankID]):
            return jsonify({"success": False, "message": "Missing required fields"}), 400
        
        # Ensure quantity is an integer
        try:
            quantity = int(quantity)
        except ValueError:
            return jsonify({"success": False, "message": "Invalid quantity format"}), 400

        # Ensure hospID is an integer (removing prefix)
        try:
            hosp_id = int(user_id[3:])  # Remove 'HO-' prefix and convert to integer
        except ValueError:
            return jsonify({"success": False, "message": "Invalid hospital ID format"}), 400

        # Ensure bloodbankID is an integer
        try:
            bloodbankID = int(bloodbankID)
        except ValueError:
            return jsonify({"success": False, "message": "Invalid blood bank ID format"}), 400

        # Ensure request_date is in proper format
        request_date = datetime.strptime(request_date, "%Y-%m-%d").date()
        print("Formatted Request Date:", request_date)

        # Get the next request ID
        cursor.execute("SELECT MAX(requestID) FROM BB_REQUESTS")
        curr_req_id = cursor.fetchone()

        req_id = curr_req_id[0] + 1 if curr_req_id and curr_req_id[0] is not None else 1001
        print("New Request ID:", req_id)

        # Insert into Oracle table
        try:
            query="""
                INSERT INTO BB_REQUESTS (requestID, hospID, blood_group, bbid, units, request_Date, location) 
                VALUES (:1, :2, :3, :4, :5, TO_DATE(:6, 'YYYY-MM-DD'), :7)
                """
            params=[req_id, hosp_id, blood_type, bloodbankID, quantity, request_date.strftime('%Y-%m-%d'),location]

            if patient_id:
                query="""
                INSERT INTO BB_REQUESTS (requestID, hospID, blood_group, bbid, units, request_Date, location, pid) 
                VALUES (:1, :2, :3, :4, :5, TO_DATE(:6, 'YYYY-MM-DD'), :7, :8)
                """
                params.append(patient_id)
            cursor.execute(query, params)
            print("Query executed: ", query, " with params: ", params)
            conn.commit()
            print("Request successfully stored.")

        except Exception as e:
            return jsonify({"success": False, "message": f"Database integrity error: {str(e)}"}), 500
        except Exception as e:
            return jsonify({"success": False, "message": f"Database error: {str(e)}"}), 500

        return jsonify({"success": True, "message": "Request stored successfully"})

    except Exception as e:
        return jsonify({"success": False, "message": f"An error occurred: {str(e)}"}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/track_patient_requests', methods=['GET','POST'])
def track_patient_requests():
    results=[]
    conn=get_db_connection()
    if conn:
        cursor=conn.cursor()

    get_user_role()
    user_id = session['role_id']
    user_id=user_id[3:]
    user_id=int(user_id)
    query='''SELECT REQUEST_ID, PATIENT_ID, HOSP_ID, HOSPITAL_NAME, BLOOD_TYPE, QUANTITY
     FROM HOSP_REQUESTS WHERE HOSP_ID=? AND STATUS!='Approved' '''
    params=[user_id]

    
    if request.method == 'POST':
        patient_id=request.form.get('pid') or ""
        blood_type=request.form.get('blood_type')
        print("Patient ID: ",patient_id)

        if patient_id != "PA-":
            query+=" AND PATIENT_ID=?"
            params.append(patient_id)
        
        if blood_type:
            print("Given blood type: ", blood_type)
            query+=" AND BLOOD_TYPE=?"
            params.append(blood_type)
        
    cursor.execute(query,params)
    print("Query executed : ", query, " with params ", params)

    results=cursor.fetchall()
    cursor.close()

    return render_template("track_patient_requests.html", results=results)

@app.route('/track_request', methods=['GET', 'POST'])
def track_request():
    results = []
    locations = []
    
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor()

        # Handle form submission
        if request.method == 'POST':
            blood_type = request.form.get('blood_type', '')
            status = request.form.get('status', '')
            user_id = request.form.get('user_id', '')

            if user_id:
                user_id = user_id[3:]  # Removing 'HO-' prefix if needed
                user_id = int(user_id)
                print("New user ID:", user_id)

            query = """ 
            SELECT REQUESTID, BBID, BLOOD_GROUP, UNITS, REQUEST_DATE, LOCATION, R_STATUS 
            FROM BB_REQUESTS 
            WHERE HOSPID = ?
            """
            params = [user_id]

            if blood_type:
                query += " AND BLOOD_GROUP = ?"
                params.append(blood_type)
            if status:
                query += " AND R_STATUS = ?"
                params.append(status)

            print("Executing query:", query)
            print("With parameters:", params)

            cursor.execute(query, params)
            results = cursor.fetchall()

        cursor.close()
        connection.close()

    return render_template("track_request.html", results=results, locations=locations, user_id=session.get('user_id'))

if __name__ == '__main__':
    app.run(port=5001, debug=True)
