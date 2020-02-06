from flask import Flask, escape, request
from datetime import datetime
from pytz import timezone
from flask import jsonify
import test

# https://www.palletsprojects.com/p/flask/
app = Flask(__name__)

@app.route('/api/v1/predictions')
def prediction():
    now = datetime.now(timezone('US/Eastern'))
    year = now.year
    month = now.month
    day = now.weekday()
    hour = now.hour
    minutes = now.minute
    results = test.do_prediction(year, month, day, hour, minutes)
    return jsonify(results)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', threaded=True)