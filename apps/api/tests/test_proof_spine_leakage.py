import pytest

from app.services.proof.leakage_guard import (
    burned_seeds_from_channels,
    check_heldout_leakage,
    seeds_in_range,
)


def test_burned_set_from_channels_extracts_trailing_ints():
    channels = {
        "calibration_selector": ["calibration_20000", "calibration_20001"],
        "training": ["train_failure_19200"],
    }

    assert burned_seeds_from_channels(channels) == {20000, 20001, 19200}


def test_burned_set_includes_extra_ranges():
    burned = burned_seeds_from_channels({}, include_ranges=[(39000, 39002)])

    assert burned == {39000, 39001, 39002}


def test_burned_set_rejects_malformed_labels():
    with pytest.raises(ValueError, match="invalid seed label"):
        burned_seeds_from_channels({"training": ["train_without_seed"]})


def test_disjoint_passes():
    report = check_heldout_leakage(held_out={50000, 50001}, burned={19200, 39000})

    assert report.passed is True
    assert report.overlap == []


def test_empty_heldout_set_fails_closed():
    report = check_heldout_leakage(held_out=set(), burned={19200, 39000})

    assert report.passed is False
    assert report.held_out_count == 0


def test_overlap_fails():
    report = check_heldout_leakage(held_out={50000, 39000}, burned={39000})

    assert report.passed is False
    assert report.overlap == [39000]


def test_seeds_in_range_inclusive():
    assert seeds_in_range((50000, 50002)) == {50000, 50001, 50002}


def test_reversed_seed_range_is_invalid():
    with pytest.raises(ValueError, match="invalid seed range"):
        seeds_in_range((50002, 50000))
