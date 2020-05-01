from app import vault_auth_provider
import hvac

import pytest
from dotmap import DotMap


def test_get_credentials_returns_dictionary_with_id_and_key(credentials_from_vault):
    credentials = vault_auth_provider.get_credentials()

    assert credentials == credentials_from_vault