from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from hexquest.models import Game, Nation, HexTile, Unit
from hexquest.worldgen import generate_world

class WorldGenTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.client.login(username='testuser', password='password')

    def test_game_creation_and_world_gen(self):
        """Test that a game can be created and world generated without crashing."""
        for i in range(10):
            response = self.client.post(reverse('hexquest:create_game'), follow=True)
            self.assertEqual(response.status_code, 200)
            game = Game.objects.latest('created_at')
            
            # Start game
            response = self.client.post(
                reverse('hexquest:game_setup', kwargs={'game_id': game.id}),
                {'action': 'start_game'},
                follow=True
            )
            self.assertEqual(response.status_code, 200)
            self.assertTrue(Game.objects.get(id=game.id).is_active)
            self.assertTrue(HexTile.objects.filter(game=game).exists())
            self.assertTrue(Unit.objects.filter(game=game).exists())

    def test_world_gen_with_many_iterations(self):
        """Directly test generate_world many times to ensure stability."""
        game = Game.objects.create(name="Stability Test", width=30, height=30, seed="test")
        Nation.objects.create(game=game, player=self.user, name="Test Nation")
        
        for i in range(50):
            # We need to clear hexes between runs if we were calling it on same game, 
            # but generate_world uses bulk_create which might fail on unique constraints 
            # if we don't clear.
            HexTile.objects.filter(game=game).delete()
            Unit.objects.filter(game=game).delete()
            generate_world(game, game.width, game.height, f"seed_{i}")
            self.assertTrue(HexTile.objects.filter(game=game).exists())
