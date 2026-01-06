# Blood Donation & Blood Bank Management System

## 📌 Project Overview
This project is a **web-based Blood Donation and Blood Bank Management System** developed using **Python (Flask)**.  
It manages blood donation activities, blood inventory, donor records, hospital requests, and approval workflows through **role-based access control**.

The system is designed to be used by **multiple hospitals and blood banks** with different user roles.

---

## 👥 User Roles & Modules
The system supports the following roles:

- **Admin**
  - Manage users
  - View donation records
  - Handle system-level operations

- **Blood Bank Manager**
  - Approve blood requests
  - Manage blood inventory
  - Verify donations

- **Hospital / Patient**
  - Request blood
  - Track blood request status
  - Register patient details

- **Donor**
  - Register as a donor
  - View donation history

- **Crossmatch / Verification Specialist**
  - Verify blood compatibility

---

## 🚀 Features
- Role-based dashboards
- Blood inventory management
- Blood request and approval system
- Donor registration and tracking
- Patient blood request tracking
- Flask-based modular architecture
- Offline-friendly design (no OTP dependency)

---

## 🛠️ Technologies Used
- **Backend:** Python (Flask)
- **Frontend:** HTML, CSS
- **Database:** Oracle DB (via cx_Oracle / PyODBC)
- **Maps Integration:** Google Maps (Shortest Path)
- **Version Control:** Git & GitHub

---

Install required packages

pip install flask cx_Oracle pyodbc

Configure Database

Set Oracle DB connection details in app.py

Ensure Oracle services are running

Run the application
python run_all.py

6️⃣ Open Browser
http://localhost:5000