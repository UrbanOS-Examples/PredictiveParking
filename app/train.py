# import libraries
from os import path
import pandas as pd
import numpy as np
from datetime import datetime
from math import sqrt
import pickle

from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import cross_val_score
from sklearn.neural_network import MLPRegressor

# read cluster and zone definition file
base_dir = path.dirname(path.abspath(__file__))
zone_centroid_cluster = pd.read_csv(path.join(base_dir, "meter_config/zone_centroid_cluster_short_north.csv"))


def parking_cluster_training(model_path = None):
    # data preparation
    for cluster_id in zone_centroid_cluster.cluster_id.unique():
        if not np.isnan(cluster_id):
            print("current cluster", str(int(cluster_id)))
            zones_in_cluster = zone_centroid_cluster[zone_centroid_cluster["cluster_id"] == cluster_id]['zoneID'].values
            print("including zones", zones_in_cluster)
            trans_in_cluster = pd.DataFrame()
            for year in [2015,2016]:
                for month in list(range(1,13)):
                    year_month = str(year)+'_'+str(month)
                    trans_withBlock_group = pd.read_csv('D://OneDrive - The Ohio State University//smart columbus//parking_meter//parking_meter_short_north//'+ str(year)+'_'+str(month) +'_' +'trans_withBlock_group.csv').drop(columns = ['Unnamed: 0'])
                    trans_in_cluster_month = trans_withBlock_group[(trans_withBlock_group['zoneID'].isin(zones_in_cluster))].reset_index(drop=True)
                    trans_in_cluster_month['timestamp'] = pd.to_datetime(trans_in_cluster_month['timestamp'])
                    trans_in_cluster_month = trans_in_cluster_month.set_index("timestamp")
                    trans_in_cluster_month['availableRate'] = trans_in_cluster_month['available']/trans_in_cluster_month['pole']
                    trans_in_cluster_month = trans_in_cluster_month.between_time('08:00', '22:00', include_start = True, include_end = False)
                    trans_in_cluster_month = trans_in_cluster_month[(trans_in_cluster_month.index.dayofweek != 6)] # exclude sunday
                    trans_in_cluster = trans_in_cluster.append(trans_in_cluster_month)
            trans_in_cluster['hour'] = list(zip(trans_in_cluster.index.hour,trans_in_cluster.index.minute))
            trans_in_cluster['hour'] = trans_in_cluster.hour.astype('category')
            trans_in_cluster['dayofweek'] = trans_in_cluster.index.dayofweek.astype('category')
            trans_in_cluster['month'] = trans_in_cluster.index.month.astype('category')
            # X = pd.DataFrame(trans_in_cluster.loc[:,['pole','hour', 'dayofweek','month']])
            X = pd.DataFrame(trans_in_cluster.loc[:,['hour', 'dayofweek','month']])
            y = pd.DataFrame(trans_in_cluster['availableRate'])
            for col in X.select_dtypes(include='category').columns:
                # print(col)
                # drop_first = True removes multi-collinearity
                add_var = pd.get_dummies(X[col], prefix=col, drop_first=True)
                # Add all the columns to the model data
                X = pd.concat([X, add_var],1)
                # Drop the original column that was expanded
                X.drop(columns=[col], inplace=True)
            # print(X.head())
            print('Data ready.')


            # model training and evaluation
            y = y.values.reshape(y.shape[0])
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=666)
            # {'identity', 'logistic', 'tanh', 'relu'}
            mlp = MLPRegressor(hidden_layer_sizes=(100), activation='relu', solver='adam', alpha=0.0001,
                            batch_size='auto', learning_rate='constant', learning_rate_init=0.001, power_t=0.5,
                            max_iter=200, shuffle=True, random_state=None, tol=0.0001, verbose=False,
                            warm_start=False, momentum=0.9, nesterovs_momentum=True, early_stopping=False,
                            validation_fraction=0.3, beta_1=0.9, beta_2=0.999, epsilon=1e-08)

            print("Start training ...")
            mlp.fit(X_train, y_train)
            y_pred = mlp.predict(X_test)
            print('rmse in train', sqrt(mean_squared_error(y_train,mlp.predict(X_train))))
            print('rmse in test', sqrt(mean_squared_error(y_test, y_pred)))
            print('mae in test', mean_absolute_error(y_test, y_pred))

            print('Start cross validation ...')
            scores = cross_val_score(mlp, X_train, y_train, cv=5)

            print("each time scores are", scores)
            print("average score is", sum(scores)/len(scores))


            if model_path is not None:
                filename = model_path + "/model_cluster"  + str(int(cluster_id))
            else:
                filename = 'models/model_cluster' + str(int(cluster_id))
            pickle.dump(mlp, open(filename, 'wb'))
            print('Finished.')


if __name__ == "__main__":
    output_path = input("Output model directory:")
    if not path.isdir(output_path):
        raise OSError("Input path is not a directory.")
    print(output_path)
    try:
        parking_cluster_training(output_path)
    except:
        raise


