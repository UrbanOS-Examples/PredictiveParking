from flask import Flask, escape, request, jsonify
from datetime import datetime
from pytz import timezone
import predictor

app = Flask(__name__)

@app.route('/api/v1/predictions')
def predictions():
    now = datetime.now(timezone('US/Eastern'))
    results = predictor.predict(now)
    return jsonify(results)

if __name__ == '__main__':
    app.run()