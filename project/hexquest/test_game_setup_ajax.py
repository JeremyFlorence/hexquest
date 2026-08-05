from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from .models import Game, Nation, Friendship, Notification

class GameSetupAJAXTests(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user(username='creator', password='password')
        self.player2 = User.objects.create_user(username='player2', password='password')
        Friendship.objects.create(user=self.creator, friend=self.player2)
        
        self.client.force_login(self.creator)
        self.client.post(reverse('hexquest:create_game'))
        self.game = Game.objects.latest('created_at')

    def test_update_settings_ajax(self):
        self.client.force_login(self.creator)
        response = self.client.post(
            reverse('hexquest:game_setup', kwargs={'game_id': self.game.id}),
            {'action': 'update_settings', 'name': 'New Game Name', 'width': 20, 'height': 20, 'seed': 'newseed', 'turn_timer': 60, 'starting_gold': 100, 'starting_food': 100, 'starting_settlers': 2},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})
        
        self.game.refresh_from_db()
        self.assertEqual(self.game.name, 'New Game Name')
        self.assertEqual(self.game.width, 20)

    def test_invite_player_ajax(self):
        self.client.force_login(self.creator)
        response = self.client.post(
            reverse('hexquest:game_setup', kwargs={'game_id': self.game.id}),
            {'action': 'invite_player', 'username': 'player2'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})
        
        self.assertTrue(Notification.objects.filter(user=self.player2, game=self.game, notification_type='game_invite').exists())

    def test_update_nation_ajax(self):
        self.client.force_login(self.creator)
        response = self.client.post(
            reverse('hexquest:game_setup', kwargs={'game_id': self.game.id}),
            {'action': 'update_nation', 'nation_name': 'My Super Nation', 'color': '#ff0000'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})
        
        nation = Nation.objects.get(game=self.game, player=self.creator)
        self.assertEqual(nation.name, 'My Super Nation')
        self.assertEqual(nation.color, '#ff0000')

    def test_game_setup_updates_includes_settings(self):
        self.client.force_login(self.creator)
        response = self.client.get(reverse('hexquest:game_setup_updates', kwargs={'game_id': self.game.id}))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('settings', data)
        self.assertEqual(data['settings']['name'], self.game.name)
        self.assertEqual(data['settings']['width'], self.game.width)
