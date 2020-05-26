from os import getenv
from quart import Quart, escape, request, jsonify
import asyncio
from datetime import datetime
from pytz import timezone
from app import predictor
from app import now_adjusted
from app import model_provider
from app import availability_provider

import logging
logging.basicConfig(level=logging.INFO)

app = Quart(__name__)


@app.before_serving
async def startup():
    logging.info('starting API')
    loop = asyncio.get_event_loop()

    logging.info('scheduling availability cache to be filled from stream')
    app.model_fetcher = loop.create_task(availability_provider.listen_to_stream_forever())
    logging.info('scheduling model cache to be re-warmed periodically')
    app.model_fetcher = loop.create_task(model_provider.fetch_models_periodically())
    logging.info('finished starting API')

    logging.info('warming model cache')
    await model_provider.warm_model_caches()
    logging.info('done warming model cache')


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

    prediction_index = predictor.predict_as_index(now, zone_ids)
    availability_index = availability_provider.get_all_availability()

    predictions_and_availability = _merge_existing(prediction_index, availability_index)
    predictions_and_availability_formatted = predictor.predict_as_api_format(predictions_and_availability)

    return jsonify(predictions_and_availability_formatted)


def _merge_existing(updatee, updator):
    # return {**updatee, **updator}
    for key, value in updator.items():
        if key in updatee:
            updatee[key] = value

    return updatee


@app.route('/api/v0/predictions')
async def predictions_comparative():
    now = now_adjusted.adjust(datetime.now(timezone('US/Eastern')))
    zoneParam = request.args.get('zone_ids')
    if zoneParam != None:
        zone_ids = zoneParam.split(',')
    else:
        zone_ids = 'All'

    results = predictor.predict_with(model_provider.get_comparative_models(), now, zone_ids)
    return jsonify(results)


@app.route('/api/v1/availability')
async def availability():
    return jsonify(availability_provider.get_all_availability())


if __name__ == '__main__':
    app.run()