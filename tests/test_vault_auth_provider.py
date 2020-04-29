from app import vault_auth_provider
import hvac

import pytest
from dotmap import DotMap

def test_get_credentials_returns_dictionary_with_id_and_key(monkeypatch):
    access_key_id_from_vault = 'my_first_access_key_id'
    secret_access_key_from_vault = 'my_first_secret_key_value'
    
    def _mock_auth_kubernetes(_role, _jwt):
        return {}

    def _mock_read_secret(_path, mount_point='mp'):
        return {
            'data': {
                'aws_access_key_id': access_key_id_from_vault,
                'aws_secret_access_key': secret_access_key_from_vault
            }
        }

    def _mock_new_client(vault_url):
        return DotMap({
            'auth_kubernetes': _mock_auth_kubernetes,
            'secrets': {
                'kv': {
                    'v1': {
                        'read_secret': _mock_read_secret
                    }
                }
            }
        })

    def _mock_file_read():
        return 'fake file contents'

    def _mock_file_open(file_path):
        return DotMap({
            'read': _mock_file_read
        })

    monkeypatch.setattr(hvac, 'Client', _mock_new_client)
    monkeypatch.setattr('builtins.open', _mock_file_open)
    
    credentials = vault_auth_provider.get_credentials()

    assert credentials['aws_access_key_id'] == access_key_id_from_vault
    assert credentials['aws_secret_access_key'] == secret_access_key_from_vault
