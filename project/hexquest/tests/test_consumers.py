import asyncio
from unittest.mock import patch

from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import AnonymousUser, User
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from hexquest import consumers
from hexquest.consumers import ChatConsumer, GameConsumer, SetupConsumer
from hexquest.models import Game, HexTile, Nation, Settlement, Unit


class ConsumerBroadcastHelpersTests(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username="player1", password="password")
        self.user2 = User.objects.create_user(username="player2", password="password")
        self.game = Game.objects.create(
            name="Broadcast Game",
            creator=self.user1,
            width=8,
            height=8,
            seed="seed",
            is_active=False,
            starting_gold=75,
            starting_food=30,
            starting_settlers=2,
        )
        self.nation1 = Nation.objects.create(
            game=self.game,
            player=self.user1,
            name="Blue Nation",
            color="#0000ff",
            has_ended_turn=True,
            gold=30,
            food=15,
        )
        self.nation2 = Nation.objects.create(
            game=self.game,
            player=self.user2,
            name="Red Nation",
            color="#ff0000",
        )

    def test_dispatch_async_swallows_submit_exceptions(self):
        with patch.object(consumers._BROADCAST_EXECUTOR, "submit", side_effect=RuntimeError("boom")):
            consumers._dispatch_async(lambda: None)

    def test_dispatch_async_swallows_runner_exceptions(self):
        async def _raise():
            raise RuntimeError("boom")

        with patch.object(consumers._BROADCAST_EXECUTOR, "submit", side_effect=lambda fn: fn()):
            consumers._dispatch_async(_raise)

    def test_broadcast_setup_update_dispatches_serialized_payload(self):
        calls = []

        class FakeLayer:
            async def group_send(self, group_name, event):
                calls.append((group_name, event))

        with patch("hexquest.consumers.get_channel_layer", return_value=FakeLayer()):
            with patch("hexquest.consumers._dispatch_async", side_effect=lambda coro: asyncio.run(coro())):
                consumers.broadcast_setup_update(self.game)

        self.assertEqual(len(calls), 1)
        group_name, event = calls[0]
        self.assertEqual(group_name, f"setup_game_{self.game.id}")
        self.assertEqual(event["type"], "setup.update")
        self.assertEqual(event["payload"]["settings"]["name"], self.game.name)
        self.assertEqual(len(event["payload"]["nations"]), 2)

    def test_broadcast_setup_abandoned_dispatches(self):
        calls = []

        class FakeLayer:
            async def group_send(self, group_name, event):
                calls.append((group_name, event))

        with patch("hexquest.consumers.get_channel_layer", return_value=FakeLayer()):
            with patch("hexquest.consumers._dispatch_async", side_effect=lambda coro: asyncio.run(coro())):
                consumers.broadcast_setup_abandoned(self.game.id)

        self.assertEqual(calls, [(f"setup_game_{self.game.id}", {"type": "setup.abandoned"})])

    def test_broadcast_game_update_with_unknown_user_does_not_dispatch(self):
        outsider = User.objects.create_user(username="outsider", password="password")

        with patch("hexquest.consumers.get_channel_layer", return_value=object()):
            with patch("hexquest.consumers._dispatch_async") as dispatch_mock:
                consumers.broadcast_game_update(self.game, user=outsider)

        dispatch_mock.assert_not_called()

    def test_serialize_game_update_clamps_negative_remaining_time_and_filters_queued_actions(self):
        self.game.turn_end_time = timezone.now() - timezone.timedelta(seconds=5)
        self.game.save(update_fields=["turn_end_time"])

        Unit.objects.create(game=self.game, nation=self.nation1, q=1, r=1, unit_type="settler", queued_action={"kind": "move"})
        Unit.objects.create(game=self.game, nation=self.nation2, q=2, r=2, unit_type="infantry")
        settlement = Settlement.objects.create(
            game=self.game,
            nation=self.nation1,
            q=3,
            r=3,
            name="Blue Village",
            queued_action={"kind": "produce"},
        )
        HexTile.objects.create(game=self.game, q=3, r=3, terrain="plains", owner=self.nation1, settlement=settlement)

        payload = consumers._serialize_game_update(self.game, self.nation1)

        self.assertEqual(payload["remaining_time"], 0)
        self.assertEqual(payload["unit_count"], 1)
        self.assertEqual(len(payload["queued_actions"]), 2)
        self.assertTrue(any(action["type"] == "unit" for action in payload["queued_actions"]))
        self.assertTrue(any(action["type"] == "settlement" for action in payload["queued_actions"]))


class ConsumerSocketTests(TransactionTestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username="socket_player1", password="password")
        self.user2 = User.objects.create_user(username="socket_player2", password="password")
        self.user3 = User.objects.create_user(username="socket_player3", password="password")
        self.game = Game.objects.create(
            name="Socket Game",
            creator=self.user1,
            width=6,
            height=6,
            seed="socket-seed",
        )
        self.nation1 = Nation.objects.create(game=self.game, player=self.user1, name="Nation 1", color="#112233")
        Nation.objects.create(game=self.game, player=self.user2, name="Nation 2", color="#334455")

    async def test_chat_consumer_rejects_unauthenticated_user(self):
        communicator = WebsocketCommunicator(ChatConsumer.as_asgi(), f"/ws/chat/{self.game.id}/")
        communicator.scope["user"] = AnonymousUser()
        communicator.scope["url_route"] = {"kwargs": {"game_id": str(self.game.id)}}
        connected, _ = await communicator.connect(timeout=10)
        self.assertFalse(connected)

    async def test_chat_consumer_rejects_user_outside_game(self):
        communicator = WebsocketCommunicator(ChatConsumer.as_asgi(), f"/ws/chat/{self.game.id}/")
        communicator.scope["user"] = self.user3
        communicator.scope["url_route"] = {"kwargs": {"game_id": str(self.game.id)}}
        connected, _ = await communicator.connect(timeout=10)
        self.assertFalse(connected)

    async def test_chat_consumer_broadcasts_saved_message(self):
        communicator1 = WebsocketCommunicator(ChatConsumer.as_asgi(), f"/ws/chat/{self.game.id}/")
        communicator1.scope["user"] = self.user1
        communicator1.scope["url_route"] = {"kwargs": {"game_id": str(self.game.id)}}
        connected1, _ = await communicator1.connect(timeout=10)
        self.assertTrue(connected1)

        communicator2 = WebsocketCommunicator(ChatConsumer.as_asgi(), f"/ws/chat/{self.game.id}/")
        communicator2.scope["user"] = self.user2
        communicator2.scope["url_route"] = {"kwargs": {"game_id": str(self.game.id)}}
        connected2, _ = await communicator2.connect(timeout=10)
        self.assertTrue(connected2)

        try:
            await communicator1.send_json_to({"text": "  hello world  "})
            msg1 = await communicator1.receive_json_from(timeout=10)
            msg2 = await communicator2.receive_json_from(timeout=10)
            self.assertEqual(msg1["type"], "chat_message")
            self.assertEqual(msg2["type"], "chat_message")
            self.assertEqual(msg1["message"]["text"], "hello world")
            self.assertEqual(msg2["message"]["text"], "hello world")
            self.assertEqual(msg2["message"]["user"], self.user1.username)
        finally:
            await communicator1.disconnect()
            await communicator2.disconnect()

    async def test_game_consumer_connect_returns_initial_payload(self):
        await sync_to_async(Unit.objects.create)(game=self.game, nation=self.nation1, q=0, r=0, unit_type="infantry")

        communicator = WebsocketCommunicator(GameConsumer.as_asgi(), f"/ws/game/{self.game.id}/")
        communicator.scope["user"] = self.user1
        communicator.scope["url_route"] = {"kwargs": {"game_id": str(self.game.id)}}
        connected, _ = await communicator.connect(timeout=10)
        self.assertTrue(connected)

        try:
            initial = await communicator.receive_json_from(timeout=10)
            self.assertEqual(initial["type"], "game_update")
            self.assertEqual(initial["payload"]["unit_count"], 1)
            self.assertIn("units", initial["payload"])
        finally:
            await communicator.disconnect()

    async def test_game_consumer_rejects_user_without_nation(self):
        communicator = WebsocketCommunicator(GameConsumer.as_asgi(), f"/ws/game/{self.game.id}/")
        communicator.scope["user"] = self.user3
        communicator.scope["url_route"] = {"kwargs": {"game_id": str(self.game.id)}}
        connected, _ = await communicator.connect(timeout=10)
        self.assertFalse(connected)
