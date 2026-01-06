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
import googlemaps

app = Flask(__name__)
app.secret_key='mysecretkey'

API_KEY = "AIzaSyBuUE3VDoS9iZl-o6MqZZ1e-th7CyeYiq8"
SESSION_API_URL = "http://127.0.0.1:5000/get_user_role"
gmaps = googlemaps.Client(key=API_KEY)

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
    
def get_db_connection():
    return pyodbc.connect('DSN=oracle;UID=system;PWD=0608', autocommit=True)

@app.route('/')
def check_working():
    flash_messages = {category: message for category, message in get_flashed_messages(with_categories=True)}
    return render_template('register_donor_deets.html', flash_messages=flash_messages)

@app.route('/register_donor_deets', methods=['GET', 'POST'])
def register_donor_deets():
    return render_template('register_donor_deets.html')  # or your logic

@app.route('/submit_donor', methods=['POST'])
def submit_donor():
    conn = get_db_connection()
    cursor = conn.cursor()
    donor_data = request.get_json()
    eligibility = []

    # 1. Fix DATE fields
    date_of_birth_str = donor_data.get('DateOfBirth')
    if date_of_birth_str:
        donor_data['DateOfBirth'] = datetime.strptime(date_of_birth_str, "%Y-%m-%d").date()

    last_date_str = donor_data.get('LastDonationDate')
    if last_date_str and last_date_str.strip() != "":
        last_date = datetime.strptime(last_date_str, "%Y-%m-%d").date()
        donor_data['LastDonationDate'] = last_date
        today = datetime.now().date()
        days_since_last_donation = (today - last_date).days

        if days_since_last_donation >= 112:
            eligibility.append("Double Red Cell")
        if days_since_last_donation >= 56:
            eligibility.append("Whole Blood")
        if days_since_last_donation >= 28:
            eligibility.append("Plasma")
        if days_since_last_donation >= 7:
            eligibility.append("Platelets")
    else:
        donor_data['LastDonationDate'] = None
        eligibility.extend(["Double Red Cell", "Whole Blood", "Plasma", "Platelets"])

    # 2. Fix optional text fields
    donor_data['ChronicDiseases'] = donor_data.get('ChronicDiseases') or None
    donor_data['Medications'] = donor_data.get('Medications') or None

    # 3. Fix NUMBER fields
    weight = donor_data.get('Weight')
    hemoglobin = donor_data.get('HemoglobinLevel')
    donor_data['Weight'] = Decimal(weight) if weight else None
    donor_data['HemoglobinLevel'] = Decimal(hemoglobin) if hemoglobin else None

    # 4. Prepare query and values
    query = '''
        INSERT INTO DONORS (
            DONORID, FULLNAME, DATEOFBIRTH, GENDER, BLOODGROUP,
            PHONENUMBER, EMAIL, ADDRESS, CITY, LASTDONATIONDATE,
            WEIGHT, HEMOGLOBINLEVEL, CHRONICDISEASES, MEDICATIONS,
            COVIDVACCINATIONSTATUS, ELIGIBLETODONATE, STATUS
        )
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    '''

    params = [
        donor_data['DonorID'],
        donor_data['FullName'],
        donor_data['DateOfBirth'],
        donor_data.get('Gender'),
        donor_data.get('BloodGroup'),
        donor_data['PhoneNumber'],
        donor_data.get('Email'),
        donor_data.get('Address'),
        donor_data.get('City'),
        donor_data.get('LastDonationDate'),
        donor_data.get('Weight'),
        donor_data.get('HemoglobinLevel'),
        donor_data.get('ChronicDiseases'),
        donor_data.get('Medications'),
        donor_data.get('CovidVaccinationStatus'),
        ", ".join(eligibility),
        "Active"
    ]

    print("Query:", query)
    print("Params:", params)
    cursor.execute(query, params)

    print("Donor Data Received:")
    for key, value in donor_data.items():
        print(f"{key}: {value}")

    conn.commit()
    conn.close()

    return jsonify({"status": "success", "message": "Donor data received successfully, return to dashboard!"})

@app.route('/find_bb_to_donate', methods=['GET', 'POST'])
def find_bb_to_donate():
    results = []  # To store query results
    locations = []  # To store unique locations from DB
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor()

    user_id=session.get("user_id")
    print("Donor ID: ", user_id)
    query="SELECT BLOODGROUP FROM DONORS WHERE DONORID = ?"
    params=[user_id]
    cursor.execute(query, params)
    print("Query executed: ", query, " with params: ", params)
    donor_grp=cursor.fetchone()
    donor_grp=donor_grp[0]
    if request.method == 'POST':
        latitude=request.form.get('latitude')
        longitude=request.form.get('longitude')
        latitude = float(latitude)
        longitude = float(longitude)
        coord=(latitude,longitude)
        print("Coord: ",coord)
        blood_type=request.form.get('blood_type')
        address=request.form.get('address')
        if address and address.strip():
            latitude, longitude = get_coordinates(address)
            print("Latitude: ",latitude ,"Longitude: ",longitude)
            if(latitude!=None):
                coord=(latitude,longitude)
        print("Donor location: ", latitude, " ",longitude)
        query = """ 
               SELECT BB.BBNAME, BB.LOCATION, BB.LATITUDE, BB.LONGITUDE, BB.CONTACT_NUMBER, B.B_GROUP, B.UNITS 
               FROM BLOOD_BANK_NAMELIST BB JOIN BLOOD_BANK_LIST B ON BB.BBID = B.BID AND B.B_GROUP = ?;"""
        params = [blood_type]
        cursor.execute(query, params)
        print("BLOOD BANK QUERY EXECUTED SUCCESSFULLY")
        results = cursor.fetchall()
        #print(results)

        # **Step 3: Extract coordinates for API call**
        bank_locations = [(bank[2],bank[3]) for bank in results]

        # **Step 4: Get distance matrix**
        distances = gmaps.distance_matrix(origins=[coord], destinations=bank_locations, mode="driving")

        # **Step 5: Attach distance to each blood bank and sort them**
        # Convert tuple results into dictionaries
        formatted_results = [
            {
                "bb_name": bank[0],
                "location": bank[1],
                "latitude": bank[2],
                "longitude": bank[3],
                "contact": bank[4],
                "b_group": bank[5],
                "units": bank[6]
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
            "find_bb_to_donate.html",
            results=formatted_results,
            user_id=session.get("user_id"),
            nearest_blood_bank=formatted_results[0],
            latitude=latitude,
            longitude=longitude,
            blood_type=donor_grp
        )
    
    
    return render_template("find_bb_to_donate.html", user_id=session.get("user_id"), blood_type=donor_grp)

@app.route('/track_donations', methods=['GET','POST'])
def track_donations():
    try:
        results = []
        get_user_role()
        user_id = session['role_id']
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()

        # Handle form submission
        if request.method == 'POST':
            donation_type_str = request.form.get('donationtype', '')
            print("Donation_type: ", donation_type_str)

            # Convert to a clean list
            donation_type_list = [dt.strip() for dt in donation_type_str.split(',') if dt.strip()]

            # Start with base query
            query = "SELECT DONATION_TYPE, UNITS, DONATED_DATE FROM DONATIONS WHERE DONOR_ID = ?"
            params = [user_id]

            if donation_type_list:
                # Create a placeholder for each donation type
                placeholders = ','.join(['?'] * len(donation_type_list))  # (?, ?, ?)
                query += f" AND DONATION_TYPE IN ({placeholders})"
                params.extend(donation_type_list)

            print("Query:", query)
            print("Params:", params)

            cursor.execute(query, params)
            results = cursor.fetchall()
            cursor.close()

        return render_template("track_donations.html", results=results)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500  # Return error message if failure
    
@app.route('/check_if_eligible', methods=['GET','POST'])
def check_if_eligible():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        get_user_role()
        user_id = session['role_id']
        params = []
        query = "SELECT ELIGIBLETODONATE FROM DONORS WHERE DONORID=?"
        params.append(user_id)

        cursor.execute(query, params)
        print("Query executed: ", query, " with params: ", params)
        result = cursor.fetchone()
        print("Eligible to donate? ",result)

        eligibility = {
            "Whole Blood": False,
            "Platelets": False,
            "Plasma": False, 
            "Double Red Cell": False
        }
        
        reasons = {}
        
        if result and result[0]:  # Make sure result exists and has a value
            # Parse the comma-separated list of eligible donation types
            donation_type_list = [dt.strip() for dt in result[0].split(',') if dt.strip()]
            
            # Update eligibility dictionary based on database result
            for donation_type in donation_type_list:
                if donation_type in eligibility:
                    eligibility[donation_type] = True
                else:
                    reasons[donation_type] = "You have donated this blood type recently, check the track donation for more details." 
        
        print("Eligibility: ", eligibility, " Reasons: ", reasons)
        return render_template('check_if_eligible.html', 
                               eligibility=eligibility,
                               reasons=reasons)
                                  
    except Exception as e:
        print("Error:", e)
        # Handle the error appropriately
        return render_template('check_if_eligible.html', 
                               eligibility={
                                   "Whole Blood": False,
                                   "Platelets": False,
                                   "Plasma": False,
                                   "Double Red Cell": False
                               },
                               reasons={"general": str(e)})


if __name__ == '__main__':
    app.run(port=5006, debug=True)