import pytest

from tests.fake_poco_server import FakePocoServer


@pytest.fixture
def fake_server():
    server = FakePocoServer()
    server.start()
    yield server
    server.stop()
