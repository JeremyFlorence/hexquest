from asgiref.sync import async_to_sync, sync_to_async
from channels.testing import WebsocketCommunicator
from django.test import TestCase, TransactionTestCase
from django.contrib.auth.models import User
from django.urls import reverse

from hexquest.consumers import SetupConsumer
from hexquest.models import Game, Nation


async def _connect_setup(user, game_id):
    communicator = WebsocketCommunicator(
        SetupConsumer.as_asgi(),
        f"/ws/setup/{game_id}/",
    )
    communicator.scope["user"] = user
    communicator.scope["url_route"] = {"kwargs": {"game_id": str(game_id)}}
    connected, _ = await communicator.connect()
    return communicator, connected


class AbandonGameTests(TransactionTestCase):
    def setUp(self):
        self.creator = User.objects.create_user(username='creator', password='password')
        self.player2 = User.objects.create_user(username='player2', password='password')
        
        # Creator creates a game
        self.client.force_login(self.creator)
        self.client.post(reverse('hexquest:create_game'))
        self.game = Game.objects.latest('created_at')
        
        # Player 2 joins the game
        Nation.objects.create(
            game=self.game,
            player=self.player2,
            name="Player 2 Nation",
            color="#ff0000"
        )

    async def test_creator_can_abandon_game(self):
        await sync_to_async(self.client.force_login)(self.creator)
        response = await sync_to_async(self.client.post)(
            reverse('hexquest:game_setup', kwargs={'game_id': self.game.id}),
            {'action': 'abandon_game'},
            follow=True
        )
        self.assertRedirects(response, reverse('hexquest:home'))
        self.assertFalse(await sync_to_async(Game.objects.filter(id=self.game.id).exists)())
        self.assertContains(response, "Game abandoned and deleted.")

    async def test_home_page_shows_abandoned_message_from_query_param(self):
        await sync_to_async(self.client.force_login)(self.player2)
        response = await sync_to_async(self.client.get)(reverse('hexquest:home') + "?abandoned=1")
        self.assertContains(response, "The game creator has abandoned the game.")

    async def test_non_creator_cannot_abandon_game(self):
        await sync_to_async(self.client.force_login)(self.player2)
        response = await sync_to_async(self.client.post)(
            reverse('hexquest:game_setup', kwargs={'game_id': self.game.id}),
            {'action': 'abandon_game'}
        )
        # Should redirect back to game setup (or just not delete)
        self.assertTrue(await sync_to_async(Game.objects.filter(id=self.game.id).exists)())

    async def test_setup_socket_refuses_after_abandonment(self):
        # Initial: player2 can connect to the setup socket.
        communicator, connected = await _connect_setup(self.player2, self.game.id)
        try:
            self.assertTrue(connected)
        finally:
            await communicator.disconnect()

        # Creator abandons the game.
        await sync_to_async(self.client.force_login)(self.creator)
        await sync_to_async(self.client.post)(
            reverse('hexquest:game_setup', kwargs={'game_id': self.game.id}),
            {'action': 'abandon_game'}
        )

        # A new connection is now rejected (game no longer exists).
        communicator, connected = await _connect_setup(self.player2, self.game.id)
        try:
            self.assertFalse(connected)
        finally:
            await communicator.disconnect()
