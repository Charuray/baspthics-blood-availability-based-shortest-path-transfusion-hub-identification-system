from flask import Flask, render_template

app = Flask(__name__)

@app.route('/enter_donation')
def enter_donation():
    return render_template('enter_donation.html')

@app.route('/view_buffer')
def view_buffer():
    return render_template('view_buffer.html')

if __name__ == '__main__':
    app.run(port=5003, debug=True)
