from memos.config import HealthSettings, Settings


def test_health_settings_defaults():
    h = HealthSettings()
    assert h.heartbeat_stale_factor == 5
    assert h.heartbeat_stale_min_seconds == 120
    assert h.wake_grace_seconds == 180
    assert h.check_interval == 600
    assert h.alert_cooldown_seconds == 3600


def test_settings_has_health_block():
    s = Settings()
    assert isinstance(s.health, HealthSettings)
    assert s.health.check_interval == 600
