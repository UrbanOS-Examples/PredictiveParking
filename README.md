# PredictiveParking
This is a project to predict parking meter availability for ParkMobile.
- Environment: Python3
- Dependencies/libaries: scikit-learn 0.22.1, numpy 1.18.1, pandas 0.23.4, pyodbc 4.0.28
- How to run a prediction:

	$ python3 app/cli.py

	OR

	$ python3 app/cli.py 2020 1 17 9 52

- In each folder,<br/>

	/meter_configs &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; meter zone definitions, locations, etc. <br/>
	/models	 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; current model files <br/>
	/output	 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; the output of test.py results <br/>

# Running the application local
```bash
pip3 install -r app/requirements.txt
flask run
```

# Running tests
```bash
pytest
```
