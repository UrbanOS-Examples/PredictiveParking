import importlib

import pytest

import fybr.zone_info


def test_zone_info_module_is_deprecated():
    with pytest.deprecated_call():
        importlib.reload(fybr.zone_info)