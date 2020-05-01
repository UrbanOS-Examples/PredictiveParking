from dotmap import DotMap
import hvac


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


def _mock_file_read():
    return 'fake file contents'


def successful_token_file(file_path):
    return DotMap({
        'read': _mock_file_read
    })


def successful_hvac_client(access_key_id_from_vault, secret_access_key_from_vault):
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