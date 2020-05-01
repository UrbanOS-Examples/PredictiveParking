### this is to test the model
from datetime import datetime
import sys
from app import predictor

if __name__ == "__main__":
    if len(sys.argv) == 6:
        year = int(sys.argv[1])
        month = int(sys.argv[2])
        day = int(sys.argv[3])
        hour = int(sys.argv[4])
        minutes = int(sys.argv[5])
        input_datetime = datetime(year, month, day, hour, minutes, 0)
    else:
        if len(sys.argv) > 1:
            print("specify datetime like yyyy MM dd hh mm : 2020 02 15 10 30")
            sys.exit()
        else:
            input_datetime = datetime.now()

    print("Predicting parking availability at", input_datetime, '...')
    prediction_output = predictor.predict(input_datetime)

    if prediction_output:
        print(prediction_output)
    else:
        print('Parking availability predictions are unavailable. Predictions are only available between 8:00 and 22:00, Mondays through Saturdays.')
