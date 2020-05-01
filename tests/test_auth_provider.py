from app import auth_provider
import pytest
from mockito import when, any

import hvac
from tests.fake_vault import FakeVaultClient

import builtins
from os import path
from io import StringIO


def test_get_credentials_returns_dictionary_with_id_and_key(when):
    access_key_id_from_vault = 'my_first_access_key_id'
    secret_access_key_from_vault = 'my_first_secret_key_value'
    fake_vault_client = FakeVaultClient(
        access_key_id_from_vault,
        secret_access_key_from_vault
    )

    with when(hvac).Client(any).thenReturn(fake_vault_client), \
        when(builtins).open(any).thenReturn(StringIO('hello world')), \
        when(path).isfile(any).thenReturn(True):
        
        credentials = auth_provider.get_credentials.__wrapped__()

        assert credentials == {
            'aws_access_key_id': access_key_id_from_vault,
            'aws_secret_access_key': secret_access_key_from_vault
        }


def test_get_credentials_returns_empty_dictionary_with_no_token_file():
    credentials = auth_provider.get_credentials.__wrapped__()

    assert credentials == {}