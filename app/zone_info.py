from os import path
import pandas as pd

DIRNAME = path.dirname(path.abspath(__file__))
METER_FILE_PATH = path.join(
  DIRNAME,
  'meter_config',
  'zone_cluster16_short_north_downtown_15_19.csv'
)
ZONE_CLUSTER = pd.read_csv(METER_FILE_PATH)


def cluster_ids():
  return ZONE_CLUSTER.clusterID.unique().tolist()


def zone_cluster():
  return ZONE_CLUSTER