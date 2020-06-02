#!/usr/bin/env python3
### this is to test the model
from datetime import datetime, date, timedelta
from os import environ
import sys
import csv
from app import predictor, model_provider, auth_provider
import argparse

LOCAL_FILE_NAME = "report.csv"
S3_FILE_NAME = "reports/parking_predictions_daily.csv"

parser = argparse.ArgumentParser()
parser.add_argument("--model", help=f"The model to report on. Defaults to the current day's model: {model_provider.historical_model_name(date.today())}")

def _annotate_predictions(predictions, date, report_time, model):
    for prediction in predictions:
        prediction["time"] = date
        prediction["report_time"] = report_time
        prediction["model"] = model

    return predictions


def _bucket_for_environment():
    s3 = auth_provider.authorized_s3_resource()
    environment = environ.get('SCOS_ENV', 'dev')
    return s3.Bucket(environment + '-parking-prediction-public')


def _beginning_of_day(day):
    return day.replace(hour=0, minute=0, second=0, microsecond=0)


if __name__ == "__main__":
    args = parser.parse_args()
    model = args.model or model_provider.historical_model_name(date.today())
    model_provider.warm_model_caches_synchronously([model])

    bucket = _bucket_for_environment()
    bucket.delete_objects(Delete={'Objects': [{"Key": S3_FILE_NAME}]})

    window_start = _beginning_of_day(datetime.now() - timedelta(days=30))
    window_end = _beginning_of_day(datetime.now() + timedelta(days=30))

    semihour_cursor = window_start
    report_run = datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M:%S")

    with open(LOCAL_FILE_NAME, mode='w') as csv_file:
        fieldnames = ['zoneId', 'availabilityPrediction', 'time', 'report_time', 'model']
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        while semihour_cursor < window_end:
            semihour_cursor = semihour_cursor + timedelta(minutes=30)
            prediction_output = predictor.predict(semihour_cursor, 'All', model)
            _annotate_predictions(prediction_output, datetime.strftime(semihour_cursor, "%Y-%m-%d %H:%M:%S"), report_run, model)
            if prediction_output:
                for prediction in prediction_output:
                    writer.writerow(prediction)

    bucket.upload_file(LOCAL_FILE_NAME, S3_FILE_NAME, ExtraArgs={'ACL':'public-read'})
