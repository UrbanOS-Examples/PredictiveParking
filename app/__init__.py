from os import getenv
from flask import Flask, escape, request, jsonify
from datetime import datetime
from pytz import timezone
from app import predictor
from app import now_adjusted

import logging
logging.basicConfig(level=logging.NOTSET)

app = Flask(__name__)

@app.route('/api/v1/predictions')
def predictions():
    now = now_adjusted.adjust(datetime.now(timezone('US/Eastern')))
    zoneParam = request.args.get('zone_ids')
    if zoneParam != None:
        zone_ids = zoneParam.split(',')
    else:
        zone_ids = 'All'

    results = predictor.predict(now, zone_ids)
    return jsonify(results)

@app.route('/api/v0/predictions')
def predictions_comparative():
    now = now_adjusted.adjust(datetime.now(timezone('US/Eastern')))
    zoneParam = request.args.get('zone_ids')
    if zoneParam != None:
        zone_ids = zoneParam.split(',')
    else:
        zone_ids = 'All'

    results = predictor.predict_with(_get_comparative_models(), now, zone_ids)
    return jsonify(results)

def _get_comparative_models():
    return getenv('COMPARED_MODELS', '12month,18month,24month').split(',')

if __name__ == '__main__':
    app.run()