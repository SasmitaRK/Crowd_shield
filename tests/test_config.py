from crowdshield import config


def test_env_var_wins(monkeypatch):
    monkeypatch.setenv("CROWDSHIELD_MAX_SIDE", "900")
    assert config.default_max_side() == 900


def test_small_server_counts_at_the_small_size(monkeypatch):
    monkeypatch.delenv("CROWDSHIELD_MAX_SIDE", raising=False)
    monkeypatch.setattr(config, "on_streamlit_cloud", lambda: False)
    monkeypatch.setattr(config, "memory_limit_bytes", lambda: 3 * 1024 ** 3)
    assert config.default_max_side() == config.SMALL_SERVER_MAX_SIDE


def test_streamlit_cloud_counts_at_the_small_size(monkeypatch):
    monkeypatch.delenv("CROWDSHIELD_MAX_SIDE", raising=False)
    monkeypatch.setattr(config, "on_streamlit_cloud", lambda: True)
    monkeypatch.setattr(config, "memory_limit_bytes", lambda: 64 * 1024 ** 3)
    assert config.default_max_side() == config.SMALL_SERVER_MAX_SIDE


def test_big_machine_keeps_full_size(monkeypatch):
    monkeypatch.delenv("CROWDSHIELD_MAX_SIDE", raising=False)
    monkeypatch.setattr(config, "on_streamlit_cloud", lambda: False)
    monkeypatch.setattr(config, "memory_limit_bytes", lambda: 16 * 1024 ** 3)
    assert config.default_max_side() == config.FULL_MAX_SIDE
