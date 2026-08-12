from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
import datetime
from hexquest.models import Game, Nation, HexTile, Unit

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

    def test_turns_rotate_through_players_sequentially(self):
        """Turns should pass from one player to the next, not resolve simultaneously."""
        initial_turn = self.game.current_turn
        creator_nation = self.game.nations.get(player=self.creator)
        player2_nation = self.game.nations.get(player=self.player2)

        # The creator (first to join) goes first.
        self.assertEqual(self.game.active_nation_id, creator_nation.id)

        # Player 2 can't act or end their turn out of order.
        self.client.force_login(self.player2)
        response = self.client.post(
            reverse('hexquest:game_map', kwargs={'game_id': self.game.id}),
            {'action': 'end_turn'}
        )
        self.game.refresh_from_db()
        self.assertEqual(self.game.active_nation_id, creator_nation.id)

        # Player 1 (active) ends turn - the round isn't complete, so the turn
        # number doesn't advance, but the active player does.
        self.client.force_login(self.creator)
        self.client.post(
            reverse('hexquest:game_map', kwargs={'game_id': self.game.id}),
            {'action': 'end_turn'}
        )

        self.game.refresh_from_db()
        self.assertEqual(self.game.current_turn, initial_turn)
        self.assertEqual(self.game.active_nation_id, player2_nation.id)

        # Player 2 ends turn - the round is now complete (everyone has gone
        # once), so the turn number advances and play returns to player 1.
        self.client.force_login(self.player2)
        self.client.post(
            reverse('hexquest:game_map', kwargs={'game_id': self.game.id}),
            {'action': 'end_turn'}
        )

        self.game.refresh_from_db()
        self.assertEqual(self.game.current_turn, initial_turn + 1)
        self.assertEqual(self.game.active_nation_id, creator_nation.id)

    def test_timer_expiration_progression(self):
        """Test that turn passes to the next player when the active player's timer expires."""
        creator_nation = self.game.nations.get(player=self.creator)
        player2_nation = self.game.nations.get(player=self.player2)
        initial_turn = self.game.current_turn

        # Manually set turn_end_time to the past
        self.game.turn_end_time = timezone.now() - datetime.timedelta(seconds=1)
        self.game.save()

        # Accessing game_map should trigger turn progression to the next player.
        self.client.force_login(self.creator)
        response = self.client.get(reverse('hexquest:game_map', kwargs={'game_id': self.game.id}))

        self.game.refresh_from_db()
        self.assertEqual(self.game.current_turn, initial_turn)
        self.assertEqual(self.game.active_nation_id, player2_nation.id)
        self.assertGreater(self.game.turn_end_time, timezone.now())

        # Let player 2's timer expire too - completes the round.
        self.game.turn_end_time = timezone.now() - datetime.timedelta(seconds=1)
        self.game.save()
        self.client.force_login(self.player2)
        self.client.get(reverse('hexquest:game_map', kwargs={'game_id': self.game.id}))

        self.game.refresh_from_db()
        self.assertEqual(self.game.current_turn, initial_turn + 1)
        self.assertEqual(self.game.active_nation_id, creator_nation.id)

    def test_game_updates_endpoint(self):
        """Test the game_updates endpoint returns correct data."""
        self.client.force_login(self.creator)
        response = self.client.get(reverse('hexquest:game_updates', kwargs={'game_id': self.game.id}))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['current_turn'], self.game.current_turn)
        self.assertIn('remaining_time', data)
        self.assertIn('has_ended_turn', data)
        self.assertTrue(data['is_my_turn'])
        self.assertEqual(data['active_player_id'], self.creator.id)
