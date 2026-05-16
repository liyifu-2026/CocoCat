"""Test SceneKeeper — lightweight channel-message router."""
import pytest
from cococat.core.scene_keeper import SceneKeeper
from cococat.core.sandbox import SandboxProvider, LocalExecutor


class TestSceneKeeper:
    @pytest.mark.asyncio
    async def test_receives_message_and_calls_sandbox(self):
        """SceneKeeper receives a message, extracts identity, calls sandbox, sends reply."""
        # Mock SandboxProvider
        provider = SandboxProvider(executor=LocalExecutor())
        reply_sent = {}

        async def send_reply(user_id: str, text: str):
            reply_sent["user_id"] = user_id
            reply_sent["text"] = text

        class MockChannel:
            async def parse_identity(self, raw_msg: dict) -> str:
                return raw_msg.get("from_user", "unknown")

            async def send(self, user_id: str, text: str):
                await send_reply(user_id, text)

        channel = MockChannel()
        keeper = SceneKeeper(
            scene_id="customer-service",
            channel=channel,
            sandbox_provider=provider,
            scene_permissions={"kbs": ["faq"], "skills": ["communication"]},
        )

        msg = {"from_user": "user-42", "text": "我需要帮助"}
        await keeper.handle_message(msg)

        # Reply was sent
        assert reply_sent["user_id"] == "user-42"
        assert isinstance(reply_sent["text"], str)

    @pytest.mark.asyncio
    async def test_parses_identity_from_message(self):
        """SceneKeeper uses channel.parse_identity to get user_id."""
        provider = SandboxProvider(executor=LocalExecutor())
        users_seen = []

        class MockChannel:
            async def parse_identity(self, raw_msg: dict) -> str:
                uid = raw_msg.get("openid", "anon")
                users_seen.append(uid)
                return uid

            async def send(self, user_id: str, text: str):
                pass

        channel = MockChannel()
        keeper = SceneKeeper(
            scene_id="support",
            channel=channel,
            sandbox_provider=provider,
            scene_permissions={},
        )

        await keeper.handle_message({"openid": "wx-user-001", "text": "hello"})
        assert "wx-user-001" in users_seen

    @pytest.mark.asyncio
    async def test_scene_keeper_has_scene_id(self):
        """SceneKeeper stores its scene_id."""
        provider = SandboxProvider(executor=LocalExecutor())

        class MockChannel:
            async def parse_identity(self, raw_msg: dict) -> str: return "user-1"
            async def send(self, user_id: str, text: str): pass

        keeper = SceneKeeper(
            scene_id="customer-service",
            channel=MockChannel(),
            sandbox_provider=provider,
            scene_permissions={},
        )
        assert keeper.scene_id == "customer-service"
