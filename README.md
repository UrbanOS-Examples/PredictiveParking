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

- In each folder,<br/>

	/meter_configs &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; meter zone definitions, locations, etc. <br/>
	/models	 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; current model files <br/>
	/output	 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; the output of test.py results <br/>

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
