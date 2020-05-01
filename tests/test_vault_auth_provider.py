from app import vault_auth_provider
import hvac

import pytest
from dotmap import DotMap


def test_get_credentials_returns_dictionary_with_id_and_key(monkeypatch):
    access_key_id_from_vault = 'my_first_access_key_id'
    secret_access_key_from_vault = 'my_first_secret_key_value'

    monkeypatch.setattr(hvac, 'Client', _mock_new_hvac_client_with_creds(access_key_id_from_vault, secret_access_key_from_vault))
    monkeypatch.setattr('builtins.open', _mock_token_file_open)
    
    credentials = vault_auth_provider.get_credentials()

    assert credentials['aws_access_key_id'] == access_key_id_from_vault
    assert credentials['aws_secret_access_key'] == secret_access_key_from_vault


def _mock_auth_kubernetes(_role, _jwt):
        return {}


def _mock_read_secret(access_key_id_from_vault, secret_access_key_from_vault):
    def _closured(_path, mount_point='mp'):
        return {
            'data': {
                'aws_access_key_id': access_key_id_from_vault,
                'aws_secret_access_key': secret_access_key_from_vault
            }
        }

    return _closured

def _mock_new_hvac_client_with_creds(access_key_id_from_vault, secret_access_key_from_vault):
    def _closured(vault_url):
        return DotMap({
            'auth_kubernetes': _mock_auth_kubernetes,
            'secrets': {
                'kv': {
                    'v1': {
                        'read_secret': _mock_read_secret(access_key_id_from_vault, secret_access_key_from_vault)
                    }
                }
            }
        })

    return _closured

def _mock_file_read():
    return 'fake file contents'


def _mock_token_file_open(file_path):
    return DotMap({
        'read': _mock_file_read
    })