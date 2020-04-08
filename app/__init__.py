from flask import Flask, escape, request, jsonify
from datetime import datetime
from pytz import timezone
from app import predictor

import logging
logging.basicConfig(level=logging.NOTSET)

app = Flask(__name__)

@app.route('/api/v1/predictions')
def predictions():
    now = datetime.now(timezone('US/Eastern'))
    zoneParam = request.args.get('zone_ids')
    logging.warn(zoneParam)
    if zoneParam != None:
        zone_ids = zoneParam.split(',')
    else:
        zone_ids = 'All'

    results = predictor.predict(now, zone_ids)
    return jsonify(results)

if __name__ == '__main__':
    app.run()