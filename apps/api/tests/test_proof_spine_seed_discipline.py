from app.services.proof.contracts import SeedRangeConfig
from app.services.proof.seed_discipline import validate_seed_ranges


def _neutral_config() -> SeedRangeConfig:
    return SeedRangeConfig(
        train=(10000, 10359),
        calibration=[(20000, 20029), (30000, 30029)],
        heldout=(50000, 50049),
        pre_closure_burned=[(10000, 10359), (20000, 20029), (30000, 30029)],
    )


def test_neutral_ranges_are_disciplined_before_spend():
    report = validate_seed_ranges(_neutral_config())

    assert report.passed is True
    assert report.violations == []


def test_heldout_overlapping_train_is_rejected():
    config = _neutral_config()
    config.heldout = (10100, 10120)

    report = validate_seed_ranges(config)

    assert report.passed is False
    assert any("held-out" in violation for violation in report.violations)


def test_heldout_inside_pre_closure_burned_is_rejected():
    config = _neutral_config()
    config.pre_closure_burned = [*config.pre_closure_burned, (50000, 50049)]

    report = validate_seed_ranges(config)

    assert report.passed is False
    assert any("burned" in violation for violation in report.violations)


def test_configured_spent_no_reuse_heldout_is_rejected():
    config = _neutral_config()
    config.heldout = (40000, 40049)
    config.spent_no_reuse = [(40000, 40049)]

    report = validate_seed_ranges(config)

    assert report.passed is False
    assert any("spent/no-reuse" in violation for violation in report.violations)


def test_configured_spent_no_reuse_train_is_rejected():
    config = _neutral_config()
    config.spent_no_reuse = [(10000, 10010)]

    report = validate_seed_ranges(config)

    assert report.passed is False
    assert any("training range" in violation for violation in report.violations)


def test_configured_spent_no_reuse_calibration_is_rejected():
    config = _neutral_config()
    config.spent_no_reuse = [(30000, 30010)]

    report = validate_seed_ranges(config)

    assert report.passed is False
    assert any("calibration range" in violation for violation in report.violations)


def test_train_calibration_overlap_is_rejected():
    config = _neutral_config()
    config.calibration = [(10050, 10060)]

    report = validate_seed_ranges(config)

    assert report.passed is False
    assert any("train and calibration" in violation for violation in report.violations)
