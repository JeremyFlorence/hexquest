from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
import datetime
from .models import Game, Nation, HexTile, Unit

class TurnSystemTests(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user(username='creator', password='password')
        self.player2 = User.objects.create_user(username='player2', password='password')
        
        # Creator creates a game
        self.client.force_login(self.creator)
        self.client.post(reverse('hexquest:create_game'))
        self.game = Game.objects.latest('created_at')
        
        # Player 2 joins
        Nation.objects.create(
            game=self.game,
            player=self.player2,
            name="Player 2 Nation",
            color="#ff0000"
        )
        
        # Start game
        self.client.post(
            reverse('hexquest:game_setup', kwargs={'game_id': self.game.id}),
            {'action': 'start_game'}
        )
        self.game.refresh_from_db()

    def test_turn_timer_initialization(self):
        """Test that turn_end_time is set when game starts."""
        self.assertIsNotNone(self.game.turn_end_time)
        now = timezone.now()
        expected_end = now + datetime.timedelta(seconds=self.game.turn_timer)
        # Allow some margin for execution time
        self.assertTrue(now < self.game.turn_end_time <= expected_end + datetime.timedelta(seconds=1))

    def test_end_turn_progression(self):
        """Test that turn progresses when all players end their turn."""
        initial_turn = self.game.current_turn
        
        # Player 1 ends turn
        self.client.force_login(self.creator)
        self.client.post(
            reverse('hexquest:game_map', kwargs={'game_id': self.game.id}),
            {'action': 'end_turn'}
        )
        
        self.game.refresh_from_db()
        self.assertEqual(self.game.current_turn, initial_turn)
        self.assertTrue(self.game.nations.get(player=self.creator).has_ended_turn)
        
        # Player 2 ends turn
        self.client.force_login(self.player2)
        self.client.post(
            reverse('hexquest:game_map', kwargs={'game_id': self.game.id}),
            {'action': 'end_turn'}
        )
        
        self.game.refresh_from_db()
        self.assertEqual(self.game.current_turn, initial_turn + 1)
        # Check that has_ended_turn was reset
        self.assertFalse(self.game.nations.get(player=self.creator).has_ended_turn)
        self.assertFalse(self.game.nations.get(player=self.player2).has_ended_turn)

    def test_timer_expiration_progression(self):
        """Test that turn progresses when timer expires."""
        initial_turn = self.game.current_turn
        
        # Manually set turn_end_time to the past
        self.game.turn_end_time = timezone.now() - datetime.timedelta(seconds=1)
        self.game.save()
        
        # Accessing game_map should trigger turn progression
        self.client.force_login(self.creator)
        response = self.client.get(reverse('hexquest:game_map', kwargs={'game_id': self.game.id}))
        
        self.game.refresh_from_db()
        self.assertEqual(self.game.current_turn, initial_turn + 1)
        self.assertGreater(self.game.turn_end_time, timezone.now())

    def test_game_updates_endpoint(self):
        """Test the game_updates endpoint returns correct data."""
        self.client.force_login(self.creator)
        response = self.client.get(reverse('hexquest:game_updates', kwargs={'game_id': self.game.id}))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['current_turn'], self.game.current_turn)
        self.assertIn('remaining_time', data)
        self.assertIn('has_ended_turn', data)
