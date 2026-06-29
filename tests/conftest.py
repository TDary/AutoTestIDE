import os

import pytest

from tests.fake_poco_server import FakePocoServer


@pytest.fixture
def fake_server():
    server = FakePocoServer()
    server.start()
    yield server
    server.stop()


def pytest_addoption(parser):
    parser.addoption(
        "--run-real-device", action="store_true", default=False,
        help="Run real-device smoke tests (requires a connected Android device)",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-real-device"):
        return
    skip_real = pytest.mark.skip(reason="need --run-real-device option to run")
    for item in items:
        if "real_device" in item.keywords:
            item.add_marker(skip_real)


@pytest.fixture
def real_android_serial():
    serial = os.environ.get("AUTOTESTIDE_REAL_ANDROID_SERIAL")
    if not serial:
        pytest.skip("AUTOTESTIDE_REAL_ANDROID_SERIAL not set")
    return serial
