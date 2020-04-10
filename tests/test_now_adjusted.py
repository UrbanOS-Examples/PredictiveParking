import pytest
from datetime import datetime
from app import now_adjusted

def test_adjusts_730_to_800_to_800():
    expected = datetime(2020, 2, 7, 8, 00, 0)
    now = now_adjusted.adjust(datetime(2020, 2, 7, 7, 45, 0))

    assert now == expected

def test_adjusts_730_to_800():
    expected = datetime(2020, 2, 7, 8, 00, 0)
    now = now_adjusted.adjust(datetime(2020, 2, 7, 7, 30, 0))

    assert now == expected

def test_adjusts_2200_to_2030_to_2200():
    expected = datetime(2020, 2, 7, 22, 00, 0)
    now = now_adjusted.adjust(datetime(2020, 2, 7, 22, 9, 0))

    assert now == expected

def test_adjusts_2030_to_2200():
    expected = datetime(2020, 2, 7, 22, 00, 0)
    now = now_adjusted.adjust(datetime(2020, 2, 7, 22, 30, 0))

    assert now == expected

def below_lower_band_not_adjusted():
    expected = datetime(2020, 2, 7, 7, 29, 0)
    now = now_adjusted.adjust(datetime(2020, 2, 7, 7, 29, 0))

    assert now == expected

def above_lower_band_not_adjusted():
    expected = datetime(2020, 2, 7, 8, 1, 0)
    now = now_adjusted.adjust(datetime(2020, 2, 7, 8, 1, 0))

    assert now == expected

def above_upper_band_not_adjusted():
    expected = datetime(2020, 2, 7, 22, 31, 0)
    now = now_adjusted.adjust(datetime(2020, 2, 7, 22, 31, 0))

    assert now == expected

def below_upper_band_not_adjusted():
    expected = datetime(2020, 2, 7, 21, 59, 0)
    now = now_adjusted.adjust(datetime(2020, 2, 7, 21, 59, 0))

    assert now == expected