"""Unit tests for ChannelManager."""
import pytest
from unittest.mock import MagicMock, patch

from cococat.core.channel_manager import ChannelManager


class FakeChannel:
    def __init__(self):
        self.started = False
        self.stopped = False
        self._connect_success = True
        self.start_args = ()
        self.start_kwargs = {}
        self.on_message = None

    def start(self, *args, **kwargs):
        self.started = True
        self.start_args = args
        self.start_kwargs = kwargs

    def stop(self):
        self.stopped = True

    def wait_startup(self, timeout=0.5):
        return (self._connect_success, None if self._connect_success else "timeout")

    def send(self, *args, **kwargs):
        pass


@pytest.fixture
def ctx():
    ctx = MagicMock()
    ctx.pool = MagicMock()
    ctx.bus = MagicMock()
    ctx.sandbox_provider = MagicMock()
    ctx.config_store = MagicMock()
    return ctx


@pytest.fixture
def manager():
    return ChannelManager()


@pytest.fixture
def fake_channel():
    return FakeChannel()


class TestChannelManager:
    def test_get_status_unknown_key(self, manager):
        assert manager.get_status("nonexistent") == {}

    def test_get_status_connected_channel(self, manager):
        manager._status["main:main:test"] = {"status": "connected", "channel_type": "test"}
        assert manager.get_status("main:main:test") == {"status": "connected", "channel_type": "test"}

    def test_get_instance_unknown_key(self, manager):
        assert manager.get_instance("nonexistent") is None

    def test_get_instance_known_key(self, manager, fake_channel):
        manager._instances["main:main:test"] = fake_channel
        assert manager.get_instance("main:main:test") is fake_channel

    @patch("cococat.core.channels.factory.create_channel")
    def test_connect_creates_instance_and_status(self, mock_create, manager, ctx, fake_channel):
        mock_create.return_value = fake_channel
        manager._wire_scene = MagicMock()

        status = manager.connect("scene", "s200", "wechat", {}, ctx)

        mock_create.assert_called_once_with("wechat")
        assert manager.get_instance("scene:s200:wechat") is fake_channel
        assert manager.get_status("scene:s200:wechat")["status"] == "connected"
        assert status == {"status": "connected"}
        manager._wire_scene.assert_called_once_with(fake_channel, "s200", "wechat", ctx)

    @patch("cococat.core.channels.factory.create_channel")
    def test_connect_sets_connecting_status(self, mock_create, manager, ctx, fake_channel):
        fake_channel._connect_success = False
        mock_create.return_value = fake_channel
        manager._wire_scene = MagicMock()
        manager._watch_async = MagicMock()

        status = manager.connect("scene", "s200", "wechat", {}, ctx)

        assert status == {"status": "connecting"}
        assert manager.get_status("scene:s200:wechat")["status"] == "connecting"

    @patch("cococat.core.channels.factory.create_channel")
    def test_connect_calls_wire_main_for_main_target(self, mock_create, manager, ctx, fake_channel):
        mock_create.return_value = fake_channel
        manager._wire_main = MagicMock()

        manager.connect("main", "main", "telegram", {}, ctx)

        manager._wire_main.assert_called_once_with(fake_channel, "telegram", ctx, reuse_instance=False)

    @patch("cococat.core.channels.factory.create_channel")
    def test_connect_replaces_old_channel(self, mock_create, manager, ctx):
        old_ch = FakeChannel()
        new_ch = FakeChannel()
        mock_create.return_value = new_ch
        manager._wire_scene = MagicMock()
        manager._instances["scene:s200:wechat"] = old_ch

        manager.connect("scene", "s200", "wechat", {}, ctx)

        assert old_ch.stopped is True
        assert manager.get_instance("scene:s200:wechat") is new_ch

    def test_disconnect_removes_instance_and_status(self, manager, fake_channel):
        manager._instances["main:main:test"] = fake_channel
        manager._status["main:main:test"] = {"status": "connected"}

        manager.disconnect("main", "main", "test")

        assert "main:main:test" not in manager._instances
        assert "main:main:test" not in manager._status
        assert fake_channel.stopped is True

    def test_disconnect_nonexistent_no_error(self, manager):
        manager.disconnect("main", "main", "nonexistent")

    @patch("cococat.core.channel_manager._channel_has_credentials")
    @patch("cococat.core.channels.factory.create_channel")
    def test_auto_reconnect_skips_disabled(self, mock_create, mock_has_creds, manager, ctx):
        ctx.config_store.get_channel_configs.return_value = {
            "channels": {"telegram": {"enabled": False, "config": {"bot_token": "x"}}}
        }
        mock_has_creds.return_value = True

        manager.auto_reconnect(ctx, loop=None)

        mock_create.assert_not_called()

    @patch("cococat.core.channel_manager._channel_has_credentials")
    @patch("cococat.core.channels.factory.create_channel")
    def test_auto_reconnect_skips_no_credentials(self, mock_create, mock_has_creds, manager, ctx):
        ctx.config_store.get_channel_configs.return_value = {
            "channels": {"telegram": {"enabled": True, "config": {}}}
        }
        mock_has_creds.return_value = False

        manager.auto_reconnect(ctx, loop=None)

        mock_create.assert_not_called()

    @patch("cococat.core.channel_manager._channel_has_credentials")
    @patch("cococat.core.channels.factory.create_channel")
    def test_auto_reconnect_creates_channel(self, mock_create, mock_has_creds, manager, ctx, fake_channel):
        ctx.config_store.get_channel_configs.return_value = {
            "channels": {"telegram": {"enabled": True, "config": {"bot_token": "abc"}}}
        }
        mock_has_creds.return_value = True
        mock_create.return_value = fake_channel
        manager._wire_main = MagicMock()

        manager.auto_reconnect(ctx, loop=None)

        mock_create.assert_called_once_with("telegram")
        assert manager.get_instance("main:main:telegram") is fake_channel
        assert manager.get_status("main:main:telegram")["status"] == "connected"
        assert fake_channel.started is True
