import asyncio
import logging
from datetime import datetime

from pytz import timezone
from quart import Quart
from quart import jsonify
from quart import request

from app import model_provider
from app import now_adjusted
from app import predictor
from app import zone_info
from app.availability_provider import AvailabilityProvider

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

app = Quart(__name__)

app.availability_provider = AvailabilityProvider(
    'wss://streams.smartcolumbusos.com/socket/websocket',
    []
)


@app.before_serving
async def startup():
    LOGGER.info('starting API')
    app.availability_provider = AvailabilityProvider(
        'wss://streams.smartcolumbusos.com/socket/websocket',
        zone_info.meter_and_zone_list()
    )
    loop = asyncio.get_event_loop()

    LOGGER.info('scheduling availability cache to be filled from stream')
    app.availability_streamer = loop.create_task(app.availability_provider.handle_websocket_messages())
    LOGGER.info('scheduling model cache to be re-warmed periodically')
    app.model_fetcher = loop.create_task(model_provider.fetch_models_periodically())
    LOGGER.info('finished starting API')

    LOGGER.info('warming model cache')
    await model_provider.warm_model_caches()
    LOGGER.info('done warming model cache')


@app.after_serving
async def shutdown():
    app.model_fetcher.cancel()
    app.availability_streamer.cancel()


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

    availability = predictor.predict_as_index(now, zone_ids)

    prediction_transforms = [
        _override_availability_predictions_with_known_values,
        predictor.predict_as_api_format,
        jsonify
    ]
    for transform in prediction_transforms:
        availability = transform(availability)

    return availability


def _override_availability_predictions_with_known_values(predictions):
    sensor_data = app.availability_provider.get_all_availability()

    for key in predictions.keys() & sensor_data.keys():
        predictions[key] = sensor_data[key]
    return predictions


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
    return jsonify(app.availability_provider.get_all_availability())


if __name__ == '__main__':
    app.run()