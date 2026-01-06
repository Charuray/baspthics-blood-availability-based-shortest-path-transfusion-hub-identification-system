import subprocess
import time

apps = [
    "python main/app.py",
    "python hospital/app.py",
    "python bbmanager/app.py",
    "python dataentry/app.py",
    "python admin/app.py",
    "python patient/app.py",
    "python donor/app.py",
    "python compspe/app.py"
]

processes = []

for app in apps:
    print(f"Launching: {app}")
    p = subprocess.Popen(app, shell=True)
    processes.append(p)
    time.sleep(1)  # Give each app a second to initialize

print("All apps launched.")
print("Login page: ","http://127.0.0.1:5000")




# Keep running
for p in processes:
    p.wait()
