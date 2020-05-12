#!/usr/bin/env python3
import pandas as pd
import numpy as np
from datetime import datetime, date
from math import sqrt
import pyodbc
import pickle
import os
from os import path
import configparser
import getpass
import sys
import argparse
import logging
logging.basicConfig(level=logging.DEBUG)

from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
from sklearn.metrics import mean_absolute_error
from sklearn import preprocessing
from sklearn.model_selection import KFold
from sklearn.model_selection import cross_val_score
from sklearn.neural_network import MLPRegressor

from app import model_provider



def sql_read(server_name, db_name, sql_query, uid = None, pwd = None):
    logging.info(f"Reading data from {server_name}")
    if uid is not None and pwd is not None:
        conn_specs = 'Driver={ODBC Driver 17 for SQL Server};Server=' \
                + server_name + ';Database=' + db_name \
                + ';UID=' + uid + ';PWD=' + pwd \
                + ';'
    else:
        conn_specs = 'Driver={SQL Server Native Client 11.0};Server=' \
                    + server_name + ';Database=' + db_name \
                    + ';Trusted_Connection=yes;MARS_Connection=yes;'
    with pyodbc.connect(conn_specs) as conn:
        df = pd.read_sql_query(sql_query, conn)
    
    return df


if __name__ == "__main__":
    base_dir = path.dirname(path.abspath(__file__))

    configParser = configparser.RawConfigParser()
    configParser.read(path.join(base_dir, 'app/train.config'))
    zone_cluster = pd.read_csv(path.join(base_dir, "app/meter_config/zone_cluster16_short_north_downtown_15_19.csv"))

    environment = os.getenv('SCOS_ENV') or 'dev'
    server_name = os.getenv('SQL_SERVER_URL') or configParser.get(environment, 'mssql_url')
    db_name = os.getenv('SQL_SERVER_DATABASE') or configParser.get(environment, 'mssql_db_name')
    uid = os.getenv('SQL_SERVER_USERNAME') or configParser.get(environment, 'mssql_db_user')
    pwd = os.getenv('SQL_SERVER_PASSWORD')
    
    if pwd == None:
        pwd = getpass.getpass()
    
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
        if len(uid) > 0 and len(pwd) > 0:
            occu_df = sql_read(server_name, db_name, sql_query, uid, pwd)
        else:
            occu_df = sql_read(server_name, db_name, sql_query)
    except:
        logging.error(f"Unexpected error: {sys.exc_info()[0]}")
        raise

    if occu_df.shape[0] > 0:
        logging.info("Read data successfully.")

    logging.info(f"Records in data frame: {occu_df.shape[0]}")
    logging.info(f"Zones in data frame: {len(occu_df['zone_name'].unique())}")
   
    occu_df.loc[occu_df["no_data"] == 1, 'occu_min_rate'] = np.nan
    occu_df.loc[occu_df["no_data"] == 1, 'occu_cnt_rate'] = np.nan
    # how many of them are potential missing records (no transaction for one week for the zone), zone got bagged
    # print(occu_df.loc[(occu_df["no_trxn_one_week_flg"] == 1) & (occu_df["occu_min_rate"].notna())].shape)
    occu_df.loc[(occu_df["no_trxn_one_week_flg"] == 1) & (occu_df["occu_min_rate"].notna()), 'occu_min_rate'] =  np.nan
    occu_df.loc[(occu_df["no_trxn_one_week_flg"] == 1) & (occu_df["occu_cnt_rate"].notna()), 'occu_cnt_rate'] =  np.nan
    occu_df = occu_df.dropna(subset=['occu_cnt_rate'])
    
    models = {}

    for cluster_id in zone_cluster.clusterID.unique():
        print("\n")
        logging.info(f"Processing cluster ID {cluster_id}")

        zones_in_cluster = zone_cluster[zone_cluster["clusterID"] == cluster_id].zoneID.astype('str').values
        logging.debug(f"Zones in cluster: {zones_in_cluster}")

        occu_cluster = occu_df[occu_df['zone_name'].isin(zones_in_cluster)].reset_index(drop=True)
        
        if occu_cluster.empty:
            continue
        
        occu_cluster['semihour'] = pd.to_datetime(occu_cluster['semihour'])
        occu_cluster = occu_cluster.set_index("semihour")
        occu_cluster['available_rate'] = 1 - occu_cluster['occu_cnt_rate']
        occu_cluster = occu_cluster.between_time('08:00', '22:00', include_start = True, include_end = False) 
        occu_cluster = occu_cluster[(occu_cluster.index.dayofweek != 6)] # exclude sunday

        occu_cluster['hour'] = list(zip(occu_cluster.index.hour,occu_cluster.index.minute))
        occu_cluster['hour'] = occu_cluster.hour.astype('category')
        occu_cluster['dayofweek'] = occu_cluster.index.dayofweek.astype('category')
        occu_cluster['month'] = occu_cluster.index.month.astype('category')
        occu_cluster = occu_cluster.loc[:,['total_cnt','available_rate','hour','dayofweek','month']]
        #     X = pd.DataFrame(occu_cluster.loc[:,['total_cnt','hour', 'dayofweek','month']])
        X = pd.DataFrame(occu_cluster.loc[:,['hour', 'dayofweek','month']])
        y = pd.DataFrame(occu_cluster['available_rate'])
        # one-hot coding
        for col in X.select_dtypes(include='category').columns:
            # drop_first = True removes multi-collinearity
            add_var = pd.get_dummies(X[col], prefix=col, drop_first=True)
            # Add all the columns to the model data
            X = pd.concat([X, add_var],1)
            # Drop the original column that was expanded
            X.drop(columns=[col], inplace=True)
        logging.info(f"Total shape {X.shape}")
        
        # no meter count as feature
        # from sklearn.model_selection import cross_val_score
        # from sklearn.preprocessing import MinMaxScaler
        X_train, X_test, y_train, y_test = train_test_split(X.values, y.values.ravel(), test_size=0.3, random_state=42)
        logging.info(f"Train size {X_train.shape}, Test size {X_test.shape}")
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
        
    model_provider.put_all(models)