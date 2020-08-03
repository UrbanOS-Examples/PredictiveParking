#!/usr/bin/env python3
import configparser
import getpass
import logging
import os
from dataclasses import InitVar
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from datetime import timedelta
from math import sqrt
from pathlib import Path

import numpy as np
import pandas as pd
import pyodbc
from prometheus_client import CollectorRegistry
from prometheus_client import Gauge
from prometheus_client import push_to_gateway
from pytz import timezone
from sklearn.metrics import mean_absolute_error
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import KFold
from sklearn.model_selection import cross_val_score
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPRegressor
from tqdm import tqdm

from app import model_provider
from app import now_adjusted
from app import predictor
from app import zone_info

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

DIRNAME = Path(__file__).parent.absolute()


@dataclass
class SqlServerConfig:
    server: str
    database: str
    uid: InitVar[str] = None
    pwd: InitVar[str] = None

    def __post_init__(self, uid, pwd):
        if not (uid is None or pwd is None):
            self.driver = 'ODBC Driver 17 for SQL Server'
            self.uid = uid
            self.pwd = pwd
        else:
            self.driver = 'SQL Server Native Client 11.0'
            self.trusted_connection = self.mars_connection = 'yes'


def main():
    database_config = _get_database_config()

    occupancy_dataframe = _get_occupancy_data_from_database(database_config)

    models = _train_models(occupancy_dataframe)

    model_provider.put_all(models)

    _validate_variance()


def _get_database_config():
    config_parser = configparser.RawConfigParser()
    config_parser.read(DIRNAME / 'app/train.config')

    environment = os.getenv('SCOS_ENV', default='dev')
    url = os.getenv('SQL_SERVER_URL',
                    default=config_parser.get(environment, 'mssql_url'))
    database = os.getenv('SQL_SERVER_DATABASE',
                         default=config_parser.get(environment, 'mssql_db_name'))
    username = os.getenv('SQL_SERVER_USERNAME',
                         default=config_parser.get(environment, 'mssql_db_user'))
    password = os.getenv('SQL_SERVER_PASSWORD')
    if password is None:
        password = getpass.getpass()

    return SqlServerConfig(url, database, username, password)


def _get_occupancy_data_from_database(database_config):
    sql_query = '''
        SELECT
            [zone_name], [semihour], [occu_min], [occu_mtr_cnt],
            [no_trxn_one_day_flg], [no_trxn_one_week_flg],
            [total_cnt],
            [occu_min_rate], [occu_cnt_rate],
            [city_holiday], [shortnorth_event],
            [no_data]
        FROM [dbo].[parking_zone_occupancy_aggr]
        WHERE CONVERT(date, semihour) >= CONVERT(date, DATEADD(month, -18, GETUTCDATE()))
        ORDER BY zone_name, semihour
    '''

    try:
        occupancy_dataframe = _sql_read(database_config, sql_query)
    except Exception as e:
        LOGGER.error(f'Unexpected error: {e}')
        raise e

    if not occupancy_dataframe.empty:
        LOGGER.info('Read data from DB into dataframe successfully.')
        LOGGER.info(f'Total (row, col) counts for dataframe: {occupancy_dataframe.shape}')
        LOGGER.info(f'Zones in dataframe: {len(occupancy_dataframe["zone_name"].unique())}')
    else:
        LOGGER.error(f'No data read from DB: {occupancy_dataframe}')
        raise Exception('No data read from DB')

    return occupancy_dataframe


def _sql_read(database_config, sql_query):
    LOGGER.info(f'Reading data from DB {database_config.server}')
    LOGGER.debug('Performing DB read with spec of %s', database_config.__dict__)

    with pyodbc.connect(**database_config.__dict__) as conn:
        return pd.read_sql_query(sql_query, conn)


def _train_models(occupancy_dataframe):
    zone_cluster = zone_info.zone_cluster()

    cleaned_occupancy_dataframe = _remove_unoccupied_timeslots(occupancy_dataframe)

    models = {}

    for cluster_id in tqdm(zone_info.cluster_ids()):
        LOGGER.info(f'Processing cluster ID {cluster_id}')

        zones_in_cluster = zone_cluster[zone_cluster['clusterID'] == cluster_id].zoneID.astype('str').values
        LOGGER.debug(f'Zones in cluster: {zones_in_cluster}')

        occupancy_for_cluster = cleaned_occupancy_dataframe[
            cleaned_occupancy_dataframe['zone_name'].isin(zones_in_cluster)
        ].reset_index(drop=True)

        if occupancy_for_cluster.empty:
            LOGGER.info(f'No data available for {cluster_id}, not creating model')
            continue

        occupancy_for_cluster['semihour'] = pd.to_datetime(occupancy_for_cluster['semihour'])
        occupancy_for_cluster = occupancy_for_cluster.set_index('semihour')
        occupancy_for_cluster['available_rate'] = 1 - occupancy_for_cluster['occu_cnt_rate']
        occupancy_for_cluster = occupancy_for_cluster.between_time('08:00', '22:00', include_start=True,
                                                                   include_end=False)
        occupancy_for_cluster = occupancy_for_cluster[
            (occupancy_for_cluster.index.dayofweek != 6)
        ]

        occupancy_for_cluster['semihour'] = list(
            zip(occupancy_for_cluster.index.hour, occupancy_for_cluster.index.minute)
        )
        occupancy_for_cluster['semihour'] = occupancy_for_cluster.semihour.astype('category')
        occupancy_for_cluster['dayofweek'] = occupancy_for_cluster.index.dayofweek.astype('category')

        occupancy_for_cluster = occupancy_for_cluster.loc[
            :, ['total_cnt', 'available_rate', 'semihour', 'dayofweek']
        ] # FIXME: Superfluous?

        X = pd.DataFrame(occupancy_for_cluster.loc[:, ['semihour', 'dayofweek']])
        y = pd.DataFrame(occupancy_for_cluster['available_rate'])

        for col in X.select_dtypes(include='category').columns:
            add_var = pd.get_dummies(X[col], prefix=col, drop_first=True)
            X = pd.concat([X, add_var], axis='columns')
            X.drop(columns=[col], inplace=True)
        LOGGER.info(f'Total (row, col) counts: {X.shape}')

        X_train, X_test, y_train, y_test = train_test_split(
            X.values,
            y.values.ravel(),
            test_size=0.3,
            random_state=42
        )  # FIXME: Fixed random_state in production?
        # FIXME: Train test split before a CV?
        LOGGER.info(f'Train (row, col) counts: {X_train.shape}')
        LOGGER.info(f'Test (row, col) counts: {X_test.shape}')

        mlp = MLPRegressor(
            hidden_layer_sizes=(50, 50),
            activation='relu',
            validation_fraction=0.3
        )

        mlp.fit(X_train, y_train)
        y_pred = mlp.predict(X_test)
        LOGGER.info(f'Root Mean Square Error in train {sqrt(mean_squared_error(y_train, mlp.predict(X_train)))}')
        LOGGER.info(f'Root Mean Square Error in test {sqrt(mean_squared_error(y_test, y_pred))}')
        LOGGER.info(f'Mean Absolute Error in test {mean_absolute_error(y_test, y_pred)}')

        # FIXME: CV after fit?
        # FIXME: Fixed random_state?
        scores = cross_val_score(
            mlp, X.values, y.values.ravel(),
            cv=KFold(n_splits=5, shuffle=True, random_state=42)
        )
        LOGGER.info(f'Each time scores are {scores}')
        LOGGER.info(f'Average score is {sum(scores) / len(scores)}')

        models[str(int(cluster_id))] = mlp

    LOGGER.info(f'Successfully trained {len(models)} models')

    return models


def _remove_unoccupied_timeslots(occupancy_dataframe):
    occupancy_dataframe.loc[occupancy_dataframe['no_data'] == 1, 'occu_min_rate'] = np.nan
    occupancy_dataframe.loc[occupancy_dataframe['no_data'] == 1, 'occu_cnt_rate'] = np.nan
    occupancy_dataframe.loc[
        (
            (occupancy_dataframe['no_trxn_one_week_flg'] == 1)
            & occupancy_dataframe['occu_min_rate'].notna()
        ),
        'occu_min_rate'
    ] = np.nan
    occupancy_dataframe.loc[
        (
            (occupancy_dataframe['no_trxn_one_week_flg'] == 1)
            & occupancy_dataframe['occu_cnt_rate'].notna()
        ),
        'occu_cnt_rate'
    ] = np.nan
    return occupancy_dataframe.dropna(subset=['occu_cnt_rate'])


def _validate_variance():
    yesterday_model = model_provider.historical_model_name(date.today() - timedelta(1))
    today_model = model_provider.historical_model_name(date.today())
    models = [yesterday_model, today_model]
    model_provider.warm_model_caches_synchronously(models)

    now = now_adjusted.adjust(datetime.now(timezone('US/Eastern')))
    today_at_ten = now.replace(hour=10)
    predictions = predictor.predict_with(models, today_at_ten)

    registry = CollectorRegistry()
    gauge = Gauge(
        'parking_model_variance',
        'Variance in prediction after new model is trained',
        registry=registry,
        labelnames=['zone']
    )
    for prediction in predictions:
        prediction_yesterday = prediction[f'{yesterday_model}Prediction']
        prediction_today = prediction[f'{today_model}Prediction']
        variance = abs(round(prediction_today - prediction_yesterday, 10))
        zone = prediction['zoneId']
        gauge.labels(zone=zone).set(variance)

    environment = os.getenv('SCOS_ENV', default='dev')
    push_to_gateway(
        f'https://pushgateway.{environment}.internal.smartcolumbusos.com',
        job='variance',
        registry=registry
    )


if __name__ == '__main__':
    main()
