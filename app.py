from flask import Flask, escape, request
from datetime import datetime
from flask import jsonify
import test

# https://www.palletsprojects.com/p/flask/
app = Flask(__name__)

@app.route('/')
def prediction():
    now = datetime.now()
    year = now.year
    month = now.month
    day = now.weekday()
    hour = now.hour - 5 #This is not a full blown solution.  we should utilize time zones
    minutes = now.minute
    results = test.do_prediction(year, month, day, hour, minutes)
    return jsonify(results)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', threaded=True)