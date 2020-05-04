import pandas as pd
import numpy as np
from datetime import datetime, date
from math import sqrt
import pyodbc
import pickle
import os
import configparser
import logging
logging.basicConfig(level=logging.NOTSET)
import getpass
import sys

from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
from sklearn.metrics import mean_absolute_error
from sklearn import preprocessing
from sklearn.model_selection import KFold
from sklearn.model_selection import cross_val_score
from sklearn.neural_network import MLPRegressor

def sql_read(server_name, db_name, sql_query, uid = None, pwd = None):
    # connect to sql server, read from a table and query, return a pandas dataframe
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
    configParser = configparser.RawConfigParser()   
    configParser.read(r'train.config')
    zone_cluster = pd.read_csv("./meter_config/zone_cluster16_short_north_downtown_15_19.csv")

    environment = input('Enter environment (dev/prod):')
    server_name = configParser.get(environment, 'mssql_url')
    db_name = configParser.get(environment, 'mssql_db_name')
    uid = configParser.get(environment, 'mssql_db_user')
    pwd = os.getenv('MSSQL_PWD')
    
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
                where year(semihour) = 2019\
                order by zone_name, semihour"

    try:
        if len(uid) > 0 and len(pwd) > 0:
            occu_df = sql_read(server_name, db_name, sql_query, uid, pwd)
        else:
            occu_df = sql_read(server_name, db_name, sql_query)
    except:
        print("Unexpected error:", sys.exc_info()[0])
        raise
        # print("Read data not successfully.")
    # print(occu_df.info())
    if occu_df.shape[0] > 0:
        print("Read data successfully.")
   
    occu_df.loc[occu_df["no_data"] == 1, 'occu_min_rate'] = np.nan
    occu_df.loc[occu_df["no_data"] == 1, 'occu_cnt_rate'] = np.nan
    # how many of them are potential missing records (no transaction for one week for the zone), zone got bagged
    # print(occu_df.loc[(occu_df["no_trxn_one_week_flg"] == 1) & (occu_df["occu_min_rate"].notna())].shape)
    occu_df.loc[(occu_df["no_trxn_one_week_flg"] == 1) & (occu_df["occu_min_rate"].notna()), 'occu_min_rate'] =  np.nan
    occu_df.loc[(occu_df["no_trxn_one_week_flg"] == 1) & (occu_df["occu_cnt_rate"].notna()), 'occu_cnt_rate'] =  np.nan
    occu_df = occu_df.dropna(subset=['occu_cnt_rate'])


    for cluster_id in zone_cluster.clusterID.unique():
        print('cluster ID', cluster_id)
        zones_in_cluster = zone_cluster[zone_cluster["clusterID"] == cluster_id].zoneID.astype('str').values
        occu_cluster = occu_df[occu_df['zone_name'].isin(zones_in_cluster)].reset_index(drop=True)
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
            # print(col)
            # drop_first = True removes multi-collinearity
            add_var = pd.get_dummies(X[col], prefix=col, drop_first=True)
            # Add all the columns to the model data
            X = pd.concat([X, add_var],1)
            # Drop the original column that was expanded
            X.drop(columns=[col], inplace=True)
        print('total shape, ', X.shape)
        
        # no meter count as feature
        # from sklearn.model_selection import cross_val_score
        # from sklearn.preprocessing import MinMaxScaler
        X_train, X_test, y_train, y_test = train_test_split(X.values, y.values.ravel(), test_size=0.3, random_state=42)
        print('train size,', X_train.shape, 'test size', X_test.shape)
        # {'identity', 'logistic', 'tanh', 'relu'}
        mlp = MLPRegressor(hidden_layer_sizes=(50, 50), activation='relu', solver='adam', alpha=0.0001, 
                        batch_size='auto', learning_rate='constant', learning_rate_init=0.001, power_t=0.5,
                        max_iter=200, shuffle=True, random_state=None, tol=0.0001, verbose=False, 
                        warm_start=False, momentum=0.9, nesterovs_momentum=True, early_stopping=False, 
                        validation_fraction=0.3, beta_1=0.9, beta_2=0.999, epsilon=1e-08)

        mlp.fit(X_train, y_train)
        y_pred = mlp.predict(X_test)
        print('rmse in train', sqrt(mean_squared_error(y_train,mlp.predict(X_train))))
        print('rmse in test', sqrt(mean_squared_error(y_test, y_pred)))
        print('mae in test', mean_absolute_error(y_test, y_pred))

        scores = cross_val_score(mlp, X.values, y.values.ravel(), cv=KFold(n_splits=5, shuffle=True,random_state=42))
        print("each time scores are", scores)
        print("average score is", sum(scores)/len(scores))
        
        # save the model to disk
        filename = 'models/mlp_shortnorth_downtown_cluster' + str(int(cluster_id))
        pickle.dump(mlp, open(filename, 'wb'))
        