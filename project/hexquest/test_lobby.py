from asgiref.sync import async_to_sync, sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import User
from django.test import TransactionTestCase
from django.urls import reverse

from .consumers import SetupConsumer
from .models import Game, Nation


async def _connect_setup(user, game_id):
    """Open a websocket to SetupConsumer as ``user`` and return (communicator, initial_payload)."""
    communicator = WebsocketCommunicator(
        SetupConsumer.as_asgi(),
        f"/ws/setup/{game_id}/",
    )
    communicator.scope["user"] = user
    communicator.scope["url_route"] = {"kwargs": {"game_id": str(game_id)}}
    connected, _ = await communicator.connect(timeout=10)
    if not connected:
        return communicator, None
    try:
        initial = await communicator.receive_json_from(timeout=10)
    except Exception as e:
        return communicator, None
    return communicator, initial


class LobbyRedirectionTests(TransactionTestCase):
    def setUp(self):
        self.creator = User.objects.create_user(username='creator', password='password')
        self.player2 = User.objects.create_user(username='player2', password='password')

        # Creator creates a game
        self.client.force_login(self.creator)
        self.client.post(reverse('hexquest:create_game'))
        self.game = Game.objects.latest('created_at')

    async def test_setup_socket_reflects_active_status(self):
        """SetupConsumer's initial payload reports game_active toggling after start_game."""
        # Player 2 joins the game
        await sync_to_async(Nation.objects.create)(
            game=self.game,
            player=self.player2,
            name="Player 2 Nation",
            color="#ff0000",
        )
        
        communicator, initial = await _connect_setup(self.player2, self.game.id)
        try:
            self.assertIsNotNone(initial)
            self.assertEqual(initial["type"], "setup_update")
            self.assertFalse(initial["payload"]["game_active"])
        finally:
            await communicator.disconnect()

        # Creator starts the game
        # Need to do this via sync client or sync_to_async if it's a regular test method
        await sync_to_async(self.client.force_login)(self.creator)
        await sync_to_async(self.client.post)(
            reverse('hexquest:game_setup', kwargs={'game_id': self.game.id}),
            {'action': 'start_game'},
        )

        communicator, initial = await _connect_setup(self.player2, self.game.id)
        try:
            self.assertIsNotNone(initial)
            self.assertTrue(initial["payload"]["game_active"])
        finally:
            await communicator.disconnect()
