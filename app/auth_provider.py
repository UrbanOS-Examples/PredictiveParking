from os import path
import hvac
from cachetools import cached, LRUCache

DEFAULT_VAULT_URL = 'http://vault.vault:8200'
DEFAULT_TOKEN_FILE_PATH = '/var/run/secrets/kubernetes.io/serviceaccount/token'


@cached(cache=LRUCache(maxsize=128))
def get_credentials(vault_role, vault_credentials_key, vault_url=DEFAULT_VAULT_URL, token_file_path=DEFAULT_TOKEN_FILE_PATH):
  if path.isfile(token_file_path):
    client = hvac.Client(vault_url)
    f = open(token_file_path)
    jwt = f.read()
    client.auth_kubernetes(vault_role, jwt)
    response = client.secrets.kv.v1.read_secret(f"smart_city/aws_keys/{vault_credentials_key}", mount_point="secrets")

    return response['data']
  
  return {}