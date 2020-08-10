# PredictiveParking
This is a project to predict parking meter availability for ParkMobile.

- Environment: Python 3.8
- Dependencies are captured in the project's [`Pipfile`](Pipfile).

- How to run a prediction:

    ```bash
    pipenv run ./cli.py
    ```
 
	or

    ```bash
    pipenv run ./cli.py 2020 1 17 9 52
    ```

## Model Information
The available parking model is really a *set* of models, trained separately for
parking predictions on different clusters of related parking meters and zones
throughout Columbus. Parking transaction data is cleansed, unified in schema,
and aggregated from a variety of data sources in the
[parking_predictor_orchestration](https://github.com/SmartColumbusOS/parking_predictor_orchestration)
repository. The output of the ETL process described therein serves as the input
for the models trained and utilized for forecasting in this repository.

### Model I/O
The availability prediction models expect to receive a list of 32 features
```python
    [tod_1, tod_2, …, tod_27, dow_1, …, dow_5]
```
where
  - `tod_1` through `tod_27` represent a one-hot encoded 30 minute interval
    between 8:00 AM and 10:00 PM,
    and
  - `dow_1` through `dow_5` represent a one-hot encoded day of the week between
    Monday and Saturday.
Both one-hot encodings represent the first value of their respective categorical
variables (that is, 8:00 AM–8:30 AM for the former and Monday for the latter) as
a zero vector to avoid perfect multicollinearity.

### Model-Related Files
  - `app/meter_configs/zone_cluster16_short_north_downtown_15_19.csv`: Contains
    the current mapping between parking zones and parking zone clusters.
  - `train.py`: The script used to define, train, and monitor the performance of
    parking availability models.
  - `report.py`: A script using a given model (the most recent by default) to
    forecast parking availability in all zones at all relevant hours of the day
    for the last and next thirty days.
  - `app/predictor.py`: The meat of the webapp, wherein a cache of models
    retrieved from S3 by `app/model_provider.py` is used to generate parking
    availability predictions.

## Local development
### Environment Setup
#### Install Python dependencies
```bash
pip3 install pipenv
pipenv install --dev
```

#### Install MicroSoft ODBC Driver 17 for SQL Server
On macOS, this can be done using Homebrew as follows:
```bash
brew tap microsoft/mssql-release https://github.com/Microsoft/homebrew-mssql-release
brew update
HOMEBREW_NO_ENV_FILTERING=1 ACCEPT_EULA=Y brew install msodbcsql17 mssql-tools
```

### Running the application locally
```bash
export QUART_APP=app:app
export QUART_DEBUG=true # if you want debug messages on slow calls, etc.
pipenv run quart run
```

### Running tests
```bash
pipenv run pytest
```
