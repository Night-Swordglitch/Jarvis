from types import SimpleNamespace

import actions.system_monitor as system_monitor


def _patch_metrics(monkeypatch, *, cpu=10.0, ram=20.0, gpu=-1.0, temp=-1.0):
    monkeypatch.setattr(system_monitor.psutil, "cpu_percent", lambda interval=None: cpu)
    monkeypatch.setattr(
        system_monitor.psutil,
        "virtual_memory",
        lambda: SimpleNamespace(percent=ram),
    )
    monkeypatch.setattr(system_monitor, "_get_gpu_usage", lambda: gpu)
    monkeypatch.setattr(system_monitor, "_get_cpu_temp", lambda: temp)


def test_resource_alerts_are_aggregated_and_rate_limited(monkeypatch):
    _patch_metrics(monkeypatch, cpu=99.0, ram=98.0, gpu=97.0, temp=90.0)
    monitor = system_monitor.SystemMonitor()
    monitor._cpu_streak = 2

    alert = monitor.check()

    assert alert is not None
    assert "CPU 99%" in alert
    assert "RAM 98%" in alert
    assert "GPU utilization 97%" in alert
    assert "CPU temperature 90°C" in alert
    assert "closing applications" not in alert.lower()
    assert "stopping processes" not in alert.lower()
    assert monitor.check() is None


def test_cpu_alert_requires_a_sustained_high_reading(monkeypatch):
    _patch_metrics(monkeypatch, cpu=99.0, ram=20.0)

    monitor = system_monitor.SystemMonitor()

    assert monitor.check() is None
    assert monitor.check() is None
    alert = monitor.check()

    assert alert is not None
    assert "CPU 99%" in alert
