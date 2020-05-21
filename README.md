# PredictiveParking
This is a project to predict parking meter availability for ParkMobile.
- Environment: Python3
- Dependencies/libaries: scikit-learn 0.22.1, numpy 1.18.1, pandas 0.23.4, pyodbc 4.0.28
```bash
pip3 install pipenv
pipenv install --dev
```
- How to run a prediction:

	$ pipenv ./cli.py

	OR

	$ pipenv ./cli.py 2020 1 17 9 52

- In each folder,<br/>

	/meter_configs &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; meter zone definitions, locations, etc. <br/>
	/models	 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; current model files <br/>
	/output	 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; the output of test.py results <br/>

# Local development
## Install dependencies
```bash
pip3 install pipenv
pipenv install --dev
```

## Running the application local
```bash
export QUART_APP=app:app
export QUART_DEBUG=true # if you want debug messages on slow calls, etc.
pipenv run quart run
```

## Running tests
```bash
pipenv run pytest
```
