from flask import Flask, render_template, request, redirect, url_for
from flask import Flask, session, jsonify
from flask_session import Session
import redis
import pyodbc
import requests
import googlemaps
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'mysecretkey'
SESSION_API_URL = "http://127.0.0.1:5000/get_user_role"
API_KEY = "AIzaSyBuUE3VDoS9iZl-o6MqZZ1e-th7CyeYiq8"
gmaps = googlemaps.Client(key=API_KEY)

blood_request_status = [
    {"status": "Pending", "desc": "Your blood request has been submitted and is awaiting processing, pleae wait until your blood sample has been screened."},
    {"status": "Screening Done", "desc": "Blood samples have been screened for compatibility."},
    {"status": "Crossmatch Done", "desc": "Crossmatch tests are underway to ensure a perfect match."},
    {"status": "Approved", "desc": "Your request has been approved and the blood is ready for dispatch."}
]
status_map = {item['status']: item['desc'] for item in blood_request_status}


def get_db_connection():
    return pyodbc.connect('DSN=ODBC_2005;UID=pingipengi;PWD=pp', autocommit=True)

def get_coordinates(address):
    api_key = "AIzaSyBuUE3VDoS9iZl-o6MqZZ1e-th7CyeYiq8"
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": address,
        "key": api_key
    }

    response = requests.get(url, params=params)
    data = response.json()

    if data["status"] == "OK":
        lat = data["results"][0]["geometry"]["location"]["lat"]
        lon = data["results"][0]["geometry"]["location"]["lng"]
        print("Google Maps Lat:", lat, "Lng:", lon)
        return lat, lon
    else:
        print("Google Geocoding failed:", data["status"])
        return None, None


role_id=None
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
    
@app.route('/find_nearest_hospital', methods=['GET', 'POST'])
def find_nearest_hospital():
    results = []  # To store query results
    locations = []  # To store unique locations from DB
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor()

    get_user_role()
    patient_id = session['role_id']
    print("Patient ID: ", patient_id )
    
        
    if request.method == 'POST':
        latitude=request.form.get('latitude')
        longitude=request.form.get('longitude')
        coord=(latitude,longitude)
        print("Coord: ",coord)
        blood_type=request.form.get('blood_type')
        quantity=request.form.get('quantity')
        address=request.form.get('address')
        if address and address.strip():
            latitude, longitude = get_coordinates(address)
            print("Latitude: ",latitude ,"Longitude: ",longitude)
            if(latitude!=None):
                coord=(latitude,longitude)
        print(f"Received coordinates: Latitude = {latitude}, Longitude = {longitude}")
        print("Patient location: ", latitude, " ",longitude)
        query = """ 
                SELECT HOSPID, HOSPNAME, LOCATION, LATITUDE, LONGITUDE FROM HOSPITAL_NAMELIST 
            """
        params = []
        cursor.execute(query, params)
        print("HOSPITAL QUERY EXECUTED SUCCESSFULLY")
        results = cursor.fetchall()
        #print(results)

        # **Step 3: Extract coordinates for API call**
        bank_locations = [(bank[3],bank[4]) for bank in results]

        # **Step 4: Get distance matrix**
        distances = gmaps.distance_matrix(origins=[coord], destinations=bank_locations, mode="driving")

        # **Step 5: Attach distance to each blood bank and sort them**
        # Convert tuple results into dictionaries
        formatted_results = [
            {
                "hosp_id": bank[0],
                "hosp_name": bank[1],
                "location": bank[2],
                "latitude": bank[3],
                "longitude": bank[4]
            }
            for bank in results[:20]
        ]

        # Fetch distances from Google Maps API
        for i, bank in enumerate(formatted_results):
            element = distances['rows'][0]['elements'][i]
            distance_text = element['distance']['text']
            distance_value = element['distance']['value']  # in meters
            duration_text = element['duration']['text']
            duration_value = element['duration']['value']  # in seconds

            bank["distance_text"] = distance_text
            bank["distance_value"] = distance_value
            bank["duration_text"] = duration_text
            bank["duration_value"] = duration_value


        # Sort results by shortest distance
        formatted_results.sort(key=lambda x: x["distance_value"])
        #print("Formatted results: ",formatted_results)
        # Render results in the HTML template
        return render_template(
            "find_nearest_hospital.html",
            results=formatted_results,
            user_id=session.get("user_id"),
            nearest_hospital=formatted_results[0],
            latitude=latitude,
            longitude=longitude
        )
    
    query="SELECT PATIENT_ID FROM HOSP_REQUESTS WHERE PATIENT_ID=?"
    params=[patient_id]
    cursor.execute(query,params)
    check= cursor.fetchone()
    if check:
        query="SELECT RESULT FROM ABSCREEN WHERE PID = ? "
        params=[patient_id]
        cursor.execute(query,params)

        print("Query executed: ", query, " with params: ", params)

        results=cursor.fetchall()
        print("Request status: ", results)

        return redirect(url_for("track_blood_request"))
    return render_template("find_nearest_hospital.html", user_id=session.get("user_id"))

@app.route('/track_blood_request', methods=['GET','POST'])
def track_blood_request():
    conn=get_db_connection()
    if conn:
        cursor=conn.cursor()
        get_user_role()
        patient=session['role_id']

        query="SELECT Status FROM HOSP_REQUESTS WHERE Patient_ID= ?"
        params=[patient]

        cursor.execute(query,params)
        status=cursor.fetchone()

        if status:
            status=status[0]
            if status == "Need Serologic Test":
                status = "Screening Done"
            if status == "Crossmatch Done":
                status = "Pending"
            if status == "EXP Crossmatch Done":
                status = "Approved"
            description = status_map.get(status, "Status not found.")
        print("Current status: ", status)
    return render_template("track_blood_request.html", status=status, desc=description)

@app.route('/submit_request', methods=['POST'])
def submit_request():
    conn = get_db_connection()
    get_user_role()
    try:
        cursor = conn.cursor()
        data = request.get_json()
        hospital_id=data.get("hosp_id")
        hosp_name=data.get("hosp_name")
        # Extract and validate fields
        user_id = session['role_id']  # Expecting string like "HO-123"
        blood_type = data.get("blood_type")
        quantity = data.get("quantity")  # Might be a string

        print(f"User ID: {user_id}, Blood Type: {blood_type}, Quantity: {quantity}, Hospital ID: {hospital_id}, Hospital Name: {hosp_name}")

        if not all([user_id, blood_type, quantity, hospital_id, hosp_name]):
            return jsonify({"success": False, "message": "Missing required fields"}), 400
        
        # Ensure quantity is an integer
        try:
            quantity = int(quantity)
        except ValueError:
            return jsonify({"success": False, "message": "Invalid quantity format"}), 400


        # Ensure bloodbankID is an integer
        try:
            print("Patient ID: ", user_id)
        except ValueError:
            return jsonify({"success": False, "message": "Invalid patient ID format"}), 400

        # Get the next request ID
        cursor.execute("SELECT MAX(request_ID) FROM HOSP_REQUESTS")
        curr_req_id = cursor.fetchone()

        req_id = curr_req_id[0] + 1 if curr_req_id and curr_req_id[0] is not None else 1001
        print("New Request ID:", req_id)

        # Insert into Oracle table
        try:
            cursor.execute(
                """
                INSERT INTO HOSP_REQUESTS (REQUEST_ID, PATIENT_ID, HOSP_ID, HOSPITAL_NAME, BLOOD_TYPE, QUANTITY) 
                VALUES (:1, :2, :3, :4, :5, :6)
                """,
                (req_id, user_id, hospital_id, hosp_name, blood_type, quantity)
            )
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
@app.route('/register_patient_details', methods=['GET','POST'])
def register_patient_details():
    conn=get_db_connection()
    if conn:
        cursor=conn.cursor()
    query="SELECT NAME FROM USER_ROLE WHERE USER_ID= ?"
    params=[session.get("user_id")]

    cursor.execute(query, params)
    print("Query executed: ", query, " with params: ", params)

    name= cursor.fetchone()
    name=name[0] 
    print("Patient name: ", name)

    return render_template("register_patient_details.html", user_id=session.get("user_id"), pname=name)
if __name__ == '__main__':
    app.run(port=5005, debug=True)