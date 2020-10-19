# PredictiveParking
This is a project to predict parking meter availability for ParkMobile.

- Environment: Python 3.8
- Dependencies are captured in the project's [`pyproject.toml`](pyproject.toml)
  file.

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
```
    [tod_1, tod_2, …, tod_27, dow_1, …, dow_5]
```
where
  - `tod_1` through `tod_27` represent a one-hot encoded 30 minute interval
    between 8:00 AM and 10:00 PM,
    and
  - `dow_1` through `dow_5` represent a one-hot encoded day of the week between
    Monday and Saturday.
Both one-hot encodings represent the first value of their respective
categorical variables (that is, 8:00 AM–8:30 AM for the former and Monday for
the latter) as a zero vector to avoid perfect multicollinearity.

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

## Getting Started
### Environment Setup
#### Install System Dependencies
The notebooks in this repository rely on `libspatialindex` for certain
calculations. This library needs to be installed to avoid problems when
installing the `dev` Python dependencies. On macOS, this can be done through
Homebrew:
```bash
    brew install spatialindex
```

#### Install Python dependencies
```bash
    pip3 install poetry
    poetry install --dev
```
If you are on OS X Catalina try this if `fbprophet` fails to install.
```bash
    pip3 install poetry
    brew install gcc@7
    CXX=/usr/local/Cellar/gcc@7/7.5.0_2/bin/g++-7 CC=/usr/local/Cellar/gcc@7/7.5.0_2/bin/gcc-7 poetry install
```

#### Install MicroSoft ODBC Driver 17 for SQL Server
On macOS, this can be done using Homebrew as follows:
```bash
    brew tap microsoft/mssql-release https://github.com/Microsoft/homebrew-mssql-release
    brew update
    HOMEBREW_NO_ENV_FILTERING=1 ACCEPT_EULA=Y brew install msodbcsql17 mssql-tools
```

#### Configure Notebooks
If you're planning on running the repository's notebooks, you'll want to enable
IPython widgets to avoid problems.
```bash
    poetry run jupyter nbextension enable --py widgetsnbextension
```

### Running the application locally
```bash
export QUART_APP=app:app
export QUART_DEBUG=true # if you want debug messages on slow calls, etc.
poetry run quart run
```

### Running tests
```bash
poetry run pytest
```

### Notes for Data Scientists
This repository has been architected in such a way there are only a few places
where changes need to be made in order to upgrade the parking availability
prediction model. These files are as follows:
- the `app.model` Python module. This is where you should implement all feature
  engineering code, model implementation code, etc. Specifically, the following
  classes must be defined
  - `ModelFeatures`: A `pydantic` model specifying all of the features expected
    by your model.
    - This class must also provide a static `from_request` method for
      converting `APIPredictionRequest` objects into `ModelFeatures`.
  - `ParkingAvailabilityModel`: This is the actual trained model. It should
    include a `predict` method that takes a `ModelFeatures` object `features`
    and returns prediction values as an iterable of `float`s where the `i`-th
    `float` gives the parking availability prediction (as a probability) for
    the parking zone with `i`-th ID in `features.zone_id`.
- the `train.py` script, which contains code to retrieve training data, train a
  model, compare its performance to its recent predecessors, and upload
  newly-trained models to cloud storage. When updating the model, changes may
  be necessary here to control
  - how features are derived from the retrieved dataset,
    - Ideally, this would be done by converting dataset records into
      `PredictionAPIRequest`s and calling `ModelFeatures.from_request` on the
      requests. If the training dataset diverges from the production data in
      structure, however, this can be an alternative location for said code.
  - the core training procedure,
  - how the model is packaged into a self-contained, serializable object for
    storage purposes.
  Other code modifications in `train.py` should only be necessary when a
  fundamental change has occurred in our data sources, how model performance is
  evaluated, etc.
- unit tests for `app.model` in `tests/test_model.py`
  - These should be largely left unmodified or expanded upon.