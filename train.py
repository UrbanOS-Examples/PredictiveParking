#!/usr/bin/env python3
import configparser
import getpass
import logging
import os
import sys
from dataclasses import InitVar
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pyodbc
from prometheus_client import CollectorRegistry
from prometheus_client import Gauge
from prometheus_client import push_to_gateway
from pytz import timezone
from sklearn.neural_network import MLPRegressor

from app import model_provider
from app import now_adjusted
from app import predictor
from app import zone_info

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)
if sys.stdout.isatty():
    LOGGER.addHandler(logging.StreamHandler(sys.stdout))

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
    config = configparser.RawConfigParser()
    config.read(DIRNAME / 'app/train.config')

    smrt_environment = os.getenv('SCOS_ENV', default='dev')
    sql_password = os.getenv('SQL_SERVER_PASSWORD') or getpass.getpass()
    return SqlServerConfig(
        server=os.getenv('SQL_SERVER_URL', config.get(smrt_environment, 'mssql_url')),
        database=os.getenv('SQL_SERVER_DATABASE', config.get(smrt_environment, 'mssql_db_name')),
        uid=os.getenv('SQL_SERVER_USERNAME', config.get(smrt_environment, 'mssql_db_user')),
        pwd=sql_password
    )


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


def _train_models(occupancy_dataframe: pd.DataFrame):
    zone_cluster = zone_info.zone_cluster()

    cleaned_occupancy_dataframe = _remove_unoccupied_timeslots(occupancy_dataframe)

    models = {}

    for cluster_id in zone_info.cluster_ids():
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
            zip(
                occupancy_for_cluster.index.hour,
                occupancy_for_cluster.index.minute
            )
        )
        occupancy_for_cluster['semihour'] = occupancy_for_cluster.semihour.astype('category')
        occupancy_for_cluster['dayofweek'] = occupancy_for_cluster.index.dayofweek.astype('category')

        X = pd.DataFrame(occupancy_for_cluster.loc[:, ['semihour', 'dayofweek']])
        y = occupancy_for_cluster.available_rate

        for col in X.select_dtypes(include='category').columns:
            add_var = pd.get_dummies(X[col], prefix=col, drop_first=True)
            X = pd.concat([X, add_var], axis='columns')
            X.drop(columns=[col], inplace=True)
        LOGGER.info(f'Total (row, col) counts: {X.shape}')

        mlp = MLPRegressor(hidden_layer_sizes=(50, 50), activation='relu')
        mlp.fit(X, y)

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
