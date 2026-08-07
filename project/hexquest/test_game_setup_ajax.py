from asgiref.sync import async_to_sync, sync_to_async
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase
from django.contrib.auth.models import User
from django.urls import reverse

from .consumers import SetupConsumer
from .models import Game, Nation, Friendship, Notification


class GameSetupAJAXTests(TransactionTestCase):
    def setUp(self):
        self.creator = User.objects.create_user(username='creator', password='password')
        self.player2 = User.objects.create_user(username='player2', password='password')
        Friendship.objects.create(user=self.creator, friend=self.player2)
        
        self.client.force_login(self.creator)
        self.client.post(reverse('hexquest:create_game'))
        self.game = Game.objects.latest('created_at')

    async def test_update_settings_ajax(self):
        await sync_to_async(self.client.force_login)(self.creator)
        response = await sync_to_async(self.client.post)(
            reverse('hexquest:game_setup', kwargs={'game_id': self.game.id}),
            {'action': 'update_settings', 'name': 'New Game Name', 'width': 20, 'height': 20, 'seed': 'newseed', 'turn_timer': 60, 'starting_gold': 100, 'starting_food': 100, 'starting_settlers': 2},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})
        
        await sync_to_async(self.game.refresh_from_db)()
        self.assertEqual(self.game.name, 'New Game Name')
        self.assertEqual(self.game.width, 20)

    async def test_invite_player_ajax(self):
        await sync_to_async(self.client.force_login)(self.creator)
        response = await sync_to_async(self.client.post)(
            reverse('hexquest:game_setup', kwargs={'game_id': self.game.id}),
            {'action': 'invite_player', 'username': 'player2'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})
        
        self.assertTrue(await sync_to_async(Notification.objects.filter(user=self.player2, game=self.game, notification_type='game_invite').exists)())

    async def test_update_nation_ajax(self):
        await sync_to_async(self.client.force_login)(self.creator)
        response = await sync_to_async(self.client.post)(
            reverse('hexquest:game_setup', kwargs={'game_id': self.game.id}),
            {'action': 'update_nation', 'nation_name': 'My Super Nation', 'color': '#ff0000'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})
        
        nation = await sync_to_async(Nation.objects.get)(game=self.game, player=self.creator)
        self.assertEqual(nation.name, 'My Super Nation')
        self.assertEqual(nation.color, '#ff0000')

    async def test_setup_socket_includes_settings(self):
        communicator = WebsocketCommunicator(
            SetupConsumer.as_asgi(),
            f"/ws/setup/{self.game.id}/",
        )
        communicator.scope["user"] = self.creator
        communicator.scope["url_route"] = {"kwargs": {"game_id": str(self.game.id)}}
        connected, _ = await communicator.connect()
        try:
            self.assertTrue(connected)
            initial = await communicator.receive_json_from()
            self.assertEqual(initial["type"], "setup_update")
            self.assertIn("settings", initial["payload"])
            self.assertEqual(initial["payload"]["settings"]["name"], self.game.name)
            self.assertEqual(initial["payload"]["settings"]["width"], self.game.width)
        finally:
            await communicator.disconnect()
