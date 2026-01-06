from flask import Flask, render_template
from flask import Flask, session, jsonify
from flask_session import Session
from flask import Flask, request, render_template, redirect, url_for, session, flash, jsonify, get_flashed_messages
import pyodbc
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'mysecretkey'

def get_db_connection():
    return pyodbc.connect('DSN=ODBC_2005;UID=pingipengi;PWD=pp', autocommit=True)
connection=get_db_connection()

@app.route('/view_donations',methods=['GET','POST'])
def view_donations():
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

            query="SELECT BID, BNAME, B_GROUP, UNITS FROM blood_bank_list WHERE 1=1 "
            params=[]
            
            if group:
                query+="AND INSTR(COMPATIBILITY,?)!=0 AND REGEXP_COUNT(COMPATIBILITY,?)!=REGEXP_COUNT(COMPATIBILITY,?)"
                params.append(group)
                params.append(blood)
                params.append(group)

            cursor.execute(query,params)
            print("Query executed: ", query, "\nParams: ", params)
            results = cursor.fetchall()

            cursor.close()
        return render_template("view_donations.html", results=results, locations=locations)


    except Exception as e:
        return jsonify({"error": str(e)}), 500  # Return error message if failure

@app.route('/manage_requests')
def manage_requests():
    return render_template('manage_requests.html')

@app.route('/manage_users',methods=['GET','POST'])
def manage_users():
    try:
        results = []
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()

        # Handle form submission
        if request.method == 'POST':
            role = request.form.get('Role_User', '')

            query="SELECT USER_ID,ROLE,NAME,PHONE,EMAIL,PASSWORD FROM user_role WHERE ROLE!='Admin'"
            params=[]
            
            if role:
                query+="AND ROLE=?"
                params.append(role)

            cursor.execute(query,params)
            print("Query executed: ", query, "\nParams: ", params)
            results = cursor.fetchall()

            cursor.close()
        return render_template("manage_users.html", results=results)


    except Exception as e:
        return jsonify({"error": str(e)}), 500  # Return error message if failure
    
@app.route('/commit_route', methods=['POST'])
def commit_route():
    try:
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()

        # Handle form submission
        if request.method == 'POST':
            cursor.commit()
            print("Commit query executed.")
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route('/delete_user',methods=['GET','POST'])
def delete_user():
    try:
        results = []
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
        data=request.get_json()
        user_id=data.get('user_id')

        query="DELETE FROM USER_ROLE WHERE USER_ID = :1 "
        params=[user_id]
        cursor.execute(query,params)
        print("Query executed: ", query, "\nParams: ", params)

        cursor.close()
        return jsonify({"success": True, "message": "User deleted"})



    except Exception as e:
        return jsonify({"error": str(e)}), 500  # Return error message if failure
    
@app.route('/add_user',methods=['GET','POST'])
def add_user():
    try:
        results = []
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
        data=request.get_json()

        query="INSERT INTO USER_ROLE (USER_ID, ROLE, NAME, PHONE, EMAIL, PASSWORD) VALUES (?,?,?,?,?,?) "
        params=list(data.values())
        print("Query: ", query, " Params: ", params)
        cursor.execute(query,params)
        print("Query executed: ", query, "\nParams: ", params)

        cursor.close()
        return jsonify({"success": True, "message": "User deleted"})



    except Exception as e:
        return jsonify({"error": str(e)}), 500  # Return error message if failure
    
@app.route('/update_user_field', methods=['POST'])
def update_user_field():
    try:
        data = request.get_json()
        user_id = data['user_id']
        field = data['field']
        value = data['value']

        allowed_fields = ['NAME', 'PHONE', 'EMAIL']  # whitelist fields for safety

        if field.upper() not in allowed_fields:
            return jsonify({"success": False, "message": "Invalid field"}), 400

        connection = get_db_connection()
        cursor = connection.cursor()

        query = f"UPDATE USER_ROLE SET {field.upper()} = :1 WHERE USER_ID = :2"
        print("Query executed: ", query, " with params ", value, " , ", user_id)
        cursor.execute(query, (value, user_id))
        connection.commit()
        cursor.close()
        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500




if __name__ == '__main__':
    app.run(port=5004, debug=True)
