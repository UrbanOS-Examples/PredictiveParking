#!/usr/bin/env python3
import pandas as pd
import numpy as np
from datetime import datetime, date
from math import sqrt
import pyodbc
import pickle
import os
from os import path
from dataclasses import dataclass
import configparser
import getpass
import sys
import logging
logging.basicConfig(level=logging.INFO)

from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
from sklearn.metrics import mean_absolute_error
from sklearn import preprocessing
from sklearn.model_selection import KFold
from sklearn.model_selection import cross_val_score
from sklearn.neural_network import MLPRegressor

from app import model_provider
from app import zone_info

DIRNAME = path.dirname(path.abspath(__file__))


def main():
    database_config = _get_database_config()

    occupancy_dataframe = _get_occupancy_data_from_database(database_config)

    models = _train_models(occupancy_dataframe)
        
    model_provider.put_all(models)


def _get_database_config():
    configParser = configparser.RawConfigParser()
    configParser.read(path.join(DIRNAME, 'app/train.config'))
    
    environment = os.getenv('SCOS_ENV') or 'dev'
    url = os.getenv('SQL_SERVER_URL') or configParser.get(environment, 'mssql_url')
    database = os.getenv('SQL_SERVER_DATABASE') or configParser.get(environment, 'mssql_db_name')
    username = os.getenv('SQL_SERVER_USERNAME') or configParser.get(environment, 'mssql_db_user')
    password = os.getenv('SQL_SERVER_PASSWORD')
    
    if password == None:
        password = getpass.getpass()

    return SqlServerConfig(url, database, username, password)


def _get_occupancy_data_from_database(database_config):
    sql_query = "SELECT [zone_name] \
                ,[semihour] \
                ,[occu_min] \
                ,[occu_mtr_cnt] \
                ,[no_trxn_one_day_flg] \
                ,[no_trxn_one_week_flg] \
                ,[total_cnt] \
                ,[occu_min_rate] \
                ,[occu_cnt_rate] \
                ,[city_holiday] \
                ,[shortnorth_event] \
                ,[no_data] \
                FROM [dbo].[parking_zone_occupancy_aggr] \
                where CONVERT(date, semihour) >= CONVERT(date, DATEADD(month, -18, GETUTCDATE()))\
                order by zone_name, semihour"

    try:
        occupancy_dataframe = _sql_read(database_config, sql_query)
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise e

    if not occupancy_dataframe.empty:
        logging.info("Read data from DB into dataframe successfully.")
        logging.info(f"Total (row, col) counts for dataframe: {occupancy_dataframe.shape}")
        logging.info(f"Zones in dataframe: {len(occupancy_dataframe['zone_name'].unique())}")
    else:
        logging.error(f"No data read from DB: {occupancy_dataframe}")
        raise Exception("No data read from DB")

    return occupancy_dataframe


def _sql_read(database_config, sql_query):
    logging.info(f"Reading data from DB {database_config.url}")

    if database_config.username is not None and database_config.password is not None:
        conn_specs = ';'.join([
            'Driver={ODBC Driver 17 for SQL Server}',
            'Server=' + database_config.url, 
            'Database=' + database_config.database,
            'UID=' + database_config.username,
            'PWD=' + database_config.password
        ])
    else:
        conn_specs = ';'.join([
            'Driver={SQL Server Native Client 11.0}',
            'Server=' + database_config.url,
            'Database=' + database_config.database,
            'Trusted_Connection=yes',
            'MARS_Connection=yes'
        ])

    logging.debug(f"Performing DB read with spec of {conn_specs}")

    with pyodbc.connect(conn_specs) as conn:
        dataframe = pd.read_sql_query(sql_query, conn)
    
    return dataframe


def _train_models(occupancy_dataframe):
    zone_cluster = zone_info.zone_cluster()
   
    cleaned_occupancy_dataframe = _remove_unoccupied_timeslots(occupancy_dataframe)
    
    models = {}

    for cluster_id in zone_info.cluster_ids():
        logging.info(f"Processing cluster ID {cluster_id}")

        zones_in_cluster = zone_cluster[zone_cluster["clusterID"] == cluster_id].zoneID.astype('str').values
        logging.debug(f"Zones in cluster: {zones_in_cluster}")

        occupancy_for_cluster = cleaned_occupancy_dataframe[cleaned_occupancy_dataframe['zone_name'].isin(zones_in_cluster)].reset_index(drop=True)
        
        if occupancy_for_cluster.empty:
            logging.info(f"No data available for {cluster_id}, not creating model")
            continue
        
        occupancy_for_cluster['semihour'] = pd.to_datetime(occupancy_for_cluster['semihour'])
        occupancy_for_cluster = occupancy_for_cluster.set_index("semihour")
        occupancy_for_cluster['available_rate'] = 1 - occupancy_for_cluster['occu_cnt_rate']
        occupancy_for_cluster = occupancy_for_cluster.between_time('08:00', '22:00', include_start = True, include_end = False) 
        occupancy_for_cluster = occupancy_for_cluster[(occupancy_for_cluster.index.dayofweek != 6)] # exclude sunday

        occupancy_for_cluster['hour'] = list(zip(occupancy_for_cluster.index.hour,occupancy_for_cluster.index.minute))
        occupancy_for_cluster['hour'] = occupancy_for_cluster.hour.astype('category')
        occupancy_for_cluster['dayofweek'] = occupancy_for_cluster.index.dayofweek.astype('category')
        occupancy_for_cluster['month'] = occupancy_for_cluster.index.month.astype('category')
        occupancy_for_cluster = occupancy_for_cluster.loc[:,['total_cnt','available_rate','hour','dayofweek','month']]
        #     X = pd.DataFrame(occupancy_for_cluster.loc[:,['total_cnt','hour', 'dayofweek','month']])
        X = pd.DataFrame(occupancy_for_cluster.loc[:,['hour', 'dayofweek','month']])
        y = pd.DataFrame(occupancy_for_cluster['available_rate'])
        # one-hot coding
        for col in X.select_dtypes(include='category').columns:
            # drop_first = True removes multi-collinearity
            add_var = pd.get_dummies(X[col], prefix=col, drop_first=True)
            # Add all the columns to the model data
            X = pd.concat([X, add_var],1)
            # Drop the original column that was expanded
            X.drop(columns=[col], inplace=True)
        logging.info(f"Total (row, col) counts: {X.shape}")
        
        # no meter count as feature
        # from sklearn.model_selection import cross_val_score
        # from sklearn.preprocessing import MinMaxScaler
        X_train, X_test, y_train, y_test = train_test_split(X.values, y.values.ravel(), test_size=0.3, random_state=42)
        logging.info(f"Train (row, col) counts: {X_train.shape}")
        logging.info(f"Test (row, col) counts: {X_test.shape}")
        # {'identity', 'logistic', 'tanh', 'relu'}
        mlp = MLPRegressor(hidden_layer_sizes=(50, 50), activation='relu', solver='adam', alpha=0.0001, 
                        batch_size='auto', learning_rate='constant', learning_rate_init=0.001, power_t=0.5,
                        max_iter=200, shuffle=True, random_state=None, tol=0.0001, verbose=False, 
                        warm_start=False, momentum=0.9, nesterovs_momentum=True, early_stopping=False, 
                        validation_fraction=0.3, beta_1=0.9, beta_2=0.999, epsilon=1e-08)

        mlp.fit(X_train, y_train)
        y_pred = mlp.predict(X_test)
        logging.info(f"Root Mean Square Error in train {sqrt(mean_squared_error(y_train,mlp.predict(X_train)))}")
        logging.info(f"Root Mean Square Error in test {sqrt(mean_squared_error(y_test, y_pred))}")
        logging.info(f"Mean Absolute Error in test {mean_absolute_error(y_test, y_pred)}")

        scores = cross_val_score(mlp, X.values, y.values.ravel(), cv=KFold(n_splits=5, shuffle=True,random_state=42))
        logging.info(f"Each time scores are {scores}")
        logging.info(f"Average score is {sum(scores)/len(scores)}")
        
        models[str(int(cluster_id))] = mlp

    logging.info(f"Successfully trained {len(models)} models")

    return models


def _remove_unoccupied_timeslots(occupancy_dataframe):
    occupancy_dataframe.loc[occupancy_dataframe["no_data"] == 1, 'occu_min_rate'] = np.nan
    occupancy_dataframe.loc[occupancy_dataframe["no_data"] == 1, 'occu_cnt_rate'] = np.nan
    # how many of them are potential missing records (no transaction for one week for the zone), zone got bagged
    # print(occupancy_dataframe.loc[(occupancy_dataframe["no_trxn_one_week_flg"] == 1) & (occupancy_dataframe["occu_min_rate"].notna())].shape)
    occupancy_dataframe.loc[(occupancy_dataframe["no_trxn_one_week_flg"] == 1) & (occupancy_dataframe["occu_min_rate"].notna()), 'occu_min_rate'] =  np.nan
    occupancy_dataframe.loc[(occupancy_dataframe["no_trxn_one_week_flg"] == 1) & (occupancy_dataframe["occu_cnt_rate"].notna()), 'occu_cnt_rate'] =  np.nan
    return occupancy_dataframe.dropna(subset=['occu_cnt_rate'])


@dataclass
class SqlServerConfig:
    url: str
    database: str
    username: str = None
    password: str = None


if __name__ == "__main__":
    main()