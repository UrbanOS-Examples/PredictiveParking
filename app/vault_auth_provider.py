import hvac

DEFAULT_VAULT_URL = 'http://vault.vault:8200'
DEFAULT_TOKEN_FILE_PATH = '/var/run/secrets/kubernetes.io/serviceaccount/token'
DEFAULT_VAULT_ROLE = 'parking-prediction-api-role'
DEFAULT_VAULT_CREDENTIALS_KEY = 'parking_prediction_api'


def get_credentials(vault_url=DEFAULT_VAULT_URL, vault_role=DEFAULT_VAULT_ROLE, vault_credentials_key=DEFAULT_VAULT_CREDENTIALS_KEY, token_file_path=DEFAULT_TOKEN_FILE_PATH):
  client = hvac.Client(vault_url)
  f = open(token_file_path)
  jwt = f.read()
  client.auth_kubernetes(vault_role, jwt)
  response = client.secrets.kv.v1.read_secret(f"smart_city/aws_keys/{vault_credentials_key}", mount_point="secrets")

  return response['data']