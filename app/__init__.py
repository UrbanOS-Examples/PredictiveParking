from os import getenv
from quart import Quart, escape, request, jsonify
import asyncio
from datetime import datetime
from pytz import timezone
from app import predictor
from app import now_adjusted
from app import model_provider

import logging
logging.basicConfig(level=logging.INFO)

app = Quart(__name__)


@app.before_serving
async def startup():
    logging.info('starting API')
    loop = asyncio.get_event_loop()

    logging.info('warming cache')
    await model_provider.warm_model_caches()
    logging.info('done warming cache')

    logging.info('scheduled cache to be re-warmed periodically')
    app.model_fetcher = loop.create_task(
        model_provider.fetch_models_periodically()
    )
    logging.info('finished starting API')


@app.after_serving
async def shutdown():
    app.model_fetcher.cancel()


@app.route('/healthcheck')
async def healthcheck():
    return 'OK'


@app.route('/api/v1/predictions')
async def predictions():
    now = now_adjusted.adjust(datetime.now(timezone('US/Eastern')))
    zoneParam = request.args.get('zone_ids')
    if zoneParam != None:
        zone_ids = zoneParam.split(',')
    else:
        zone_ids = 'All'

    results = predictor.predict(now, zone_ids)
    return jsonify(results)


@app.route('/api/v0/predictions')
async def predictions_comparative():
    now = now_adjusted.adjust(datetime.now(timezone('US/Eastern')))
    zoneParam = request.args.get('zone_ids')
    if zoneParam != None:
        zone_ids = zoneParam.split(',')
    else:
        zone_ids = 'All'

    results = predictor.predict_with(_get_comparative_models(), now, zone_ids)
    return jsonify(results)


def _get_comparative_models():
    return getenv('COMPARED_MODELS', '1month,3month,6month').split(',')


if __name__ == '__main__':
    app.run()