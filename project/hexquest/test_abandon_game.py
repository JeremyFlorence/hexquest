from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from .models import Game, Nation

class AbandonGameTests(TestCase):
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

    def test_creator_can_abandon_game(self):
        self.client.force_login(self.creator)
        response = self.client.post(
            reverse('hexquest:game_setup', kwargs={'game_id': self.game.id}),
            {'action': 'abandon_game'},
            follow=True
        )
        self.assertRedirects(response, reverse('hexquest:home'))
        self.assertFalse(Game.objects.filter(id=self.game.id).exists())
        self.assertContains(response, "Game abandoned and deleted.")

    def test_home_page_shows_abandoned_message_from_query_param(self):
        self.client.force_login(self.player2)
        response = self.client.get(reverse('hexquest:home') + "?abandoned=1")
        self.assertContains(response, "The game creator has abandoned the game.")

    def test_non_creator_cannot_abandon_game(self):
        self.client.force_login(self.player2)
        response = self.client.post(
            reverse('hexquest:game_setup', kwargs={'game_id': self.game.id}),
            {'action': 'abandon_game'}
        )
        # Should redirect back to game setup (or just not delete)
        self.assertTrue(Game.objects.filter(id=self.game.id).exists())

    def test_updates_returns_404_after_abandonment(self):
        # Initial status
        self.client.force_login(self.player2)
        response = self.client.get(reverse('hexquest:game_setup_updates', kwargs={'game_id': self.game.id}))
        self.assertEqual(response.status_code, 200)
        
        # Creator abandons
        self.client.force_login(self.creator)
        self.client.post(
            reverse('hexquest:game_setup', kwargs={'game_id': self.game.id}),
            {'action': 'abandon_game'}
        )
        
        # Check status again as player 2
        self.client.force_login(self.player2)
        response = self.client.get(reverse('hexquest:game_setup_updates', kwargs={'game_id': self.game.id}))
        self.assertEqual(response.status_code, 404)
