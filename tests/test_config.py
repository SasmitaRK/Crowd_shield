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


def test_fit_picks_the_largest_size_that_fits():
    gb = 1024 ** 3
    assert config.fit_max_side(limit_bytes=3 * gb, in_use_bytes=0, own_bytes=0, ceiling=640) == 640
    # With 16 GB free and a ceiling of 2048 the full size fits.
    assert config.fit_max_side(limit_bytes=16 * gb, in_use_bytes=0, own_bytes=0, ceiling=2048) == 2048
    # A tighter server steps the size down instead of failing.
    smaller = config.fit_max_side(limit_bytes=int(1.5 * gb), in_use_bytes=0, own_bytes=0, ceiling=2048)
    assert config.MIN_SIDE <= smaller < 640


def test_other_processes_use_up_the_budget():
    gb = 1024 ** 3
    free = config.fit_max_side(limit_bytes=3 * gb, in_use_bytes=0, own_bytes=0, ceiling=640)
    busy = config.fit_max_side(limit_bytes=3 * gb, in_use_bytes=int(1.5 * gb), own_bytes=0, ceiling=640)
    assert busy < free


def test_a_server_too_small_for_the_model_says_so():
    import pytest
    with pytest.raises(config.NotEnoughMemory, match="Run Crowd Shield on your own computer"):
        config.fit_max_side(limit_bytes=800 * 1024 ** 2, in_use_bytes=0, own_bytes=0, ceiling=640)


def test_no_memory_limit_means_the_ceiling(monkeypatch):
    assert config.fit_max_side(limit_bytes=None, ceiling=1234) == 1234
