#!/usr/bin/env python3
### this is to test the model
from datetime import datetime, date
import sys
import csv
from app import predictor

def _annotate_predictions(predictions, date, model):
    for prediction in predictions:
        prediction["time"] = date
        prediction["model"] = model

    return predictions

if __name__ == "__main__":
    model = str(sys.argv[1]) or date.today().strftime("%Y-%m-%d")
    predictions = []
    filepath = 'semihour_restricted.txt'
    with open(filepath) as fp:
        with open(f"{model}_report.csv", mode='w') as csv_file:
            fieldnames = ['zoneId', 'availabilityPrediction', 'time', 'model']
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()
            for cnt, date in enumerate(fp):
                date_to_predict = datetime.strptime(date.strip(), '%Y-%m-%d %H:%M:%S.000')
                prediction_output = predictor.predict(date_to_predict)
                annotated_predictions = _annotate_predictions(prediction_output, date.strip(), model)
                if prediction_output:
                    for prediction in prediction_output:
                        writer.writerow(prediction)
