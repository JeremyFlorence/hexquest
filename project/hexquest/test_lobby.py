from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from .models import Game, Nation

class LobbyRedirectionTests(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user(username='creator', password='password')
        self.player2 = User.objects.create_user(username='player2', password='password')
        
        # Creator creates a game
        self.client.force_login(self.creator)
        self.client.post(reverse('hexquest:create_game'))
        self.game = Game.objects.latest('created_at')
        
        # Player 2 joins the game (simulated via invite acceptance logic or direct creation)
        Nation.objects.create(
            game=self.game,
            player=self.player2,
            name="Player 2 Nation",
            color="#ff0000"
        )

    def test_game_setup_updates_reflects_active_status(self):
        """Test that game_setup_updates returns game_active: True after game is started."""
        # Log in as player 2
        self.client.force_login(self.player2)
        
        # Check initial status
        response = self.client.get(reverse('hexquest:game_setup_updates', kwargs={'game_id': self.game.id}))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['game_active'])
        
        # Creator starts the game
        self.client.force_login(self.creator)
        self.client.post(
            reverse('hexquest:game_setup', kwargs={'game_id': self.game.id}),
            {'action': 'start_game'}
        )
        
        # Check status again as player 2
        self.client.force_login(self.player2)
        response = self.client.get(reverse('hexquest:game_setup_updates', kwargs={'game_id': self.game.id}))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['game_active'])
