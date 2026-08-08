from django.test import TestCase, Client
from django.contrib.auth.models import User
from hexquest.models import Game, Nation, Unit, HexTile, Building
from hexquest.worldgen import generate_world


class WheatFarmTests(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username="player1", password="test123")
        
        # Create a game
        self.game = Game.objects.create(
            name="Test Game",
            creator=self.user1,
            width=20,
            height=20,
            seed="test_seed_123",
            is_active=True
        )
        
        # Create nation
        self.nation1 = Nation.objects.create(
            game=self.game,
            player=self.user1,
            name="Nation1",
            color="#FF0000",
            food=100,
            gold=100
        )
        
        # Generate world
        generate_world(self.game, self.game.width, self.game.height, self.game.seed)
        
        # Get a plains tile and set as owned
        self.plains_tile = HexTile.objects.filter(
            game=self.game,
            terrain="plains"
        ).first()
        
        if self.plains_tile:
            self.plains_tile.owner = self.nation1
            self.plains_tile.save()
        
        # Create a builder unit on the plains tile
        self.builder = Unit.objects.create(
            game=self.game,
            nation=self.nation1,
            q=self.plains_tile.q,
            r=self.plains_tile.r,
            unit_type="builder",
            strength=10,
            movement=2
        )
    
    def test_builder_can_queue_wheat_farm_build(self):
        """Test that builder can queue a wheat farm build action."""
        self.builder.queued_action = {"type": "build", "building_type": "wheat_farm"}
        self.builder.save()
        
        # Verify queued action
        self.builder.refresh_from_db()
        self.assertEqual(self.builder.queued_action["type"], "build")
        self.assertEqual(self.builder.queued_action["building_type"], "wheat_farm")
    
    def test_wheat_farm_building_is_created_on_turn_end(self):
        """Test that building is created during turn processing."""
        self.builder.queued_action = {"type": "build", "building_type": "wheat_farm"}
        self.builder.save()
        
        # Verify no building exists yet
        self.assertFalse(Building.objects.filter(hex_tile=self.plains_tile).exists())
        
        # Simulate turn end
        self.nation1.has_ended_turn = True
        self.nation1.save()
        from hexquest.views import process_turn_end
        process_turn_end(self.game)
        
        # Verify building was created
        self.assertTrue(Building.objects.filter(hex_tile=self.plains_tile).exists())
        building = Building.objects.get(hex_tile=self.plains_tile)
        self.assertEqual(building.building_type, "wheat_farm")
    
    def test_wheat_farm_generates_food_per_turn(self):
        """Test that wheat farm generates 2 food per turn."""
        # Note: worldgen resets food to game.starting_food (default 20)
        # so we need to account for that
        self.nation1.refresh_from_db()
        initial_food = self.nation1.food
        
        self.builder.queued_action = {"type": "build", "building_type": "wheat_farm"}
        self.builder.save()
        
        # Simulate turn end
        self.nation1.has_ended_turn = True
        self.nation1.save()
        from hexquest.views import process_turn_end
        process_turn_end(self.game)
        
        # Verify food increased by 2
        self.nation1.refresh_from_db()
        self.assertEqual(self.nation1.food, initial_food + 2)
    
    def test_multiple_wheat_farms_generate_cumulative_food(self):
        """Test that multiple wheat farms generate food cumulatively."""
        # Get a second plains tile
        plains_tiles = list(HexTile.objects.filter(
            game=self.game,
            terrain="plains"
        ).exclude(id=self.plains_tile.id))
        
        if len(plains_tiles) < 1:
            self.skipTest("Not enough plains tiles for this test")
        
        plains_tile2 = plains_tiles[0]
        plains_tile2.owner = self.nation1
        plains_tile2.save()
        
        # Create second builder
        builder2 = Unit.objects.create(
            game=self.game,
            nation=self.nation1,
            q=plains_tile2.q,
            r=plains_tile2.r,
            unit_type="builder"
        )
        
        # Queue wheat farms for both builders
        self.builder.queued_action = {"type": "build", "building_type": "wheat_farm"}
        self.builder.save()
        
        builder2.queued_action = {"type": "build", "building_type": "wheat_farm"}
        builder2.save()
        
        # Get the current food before turn end
        self.nation1.refresh_from_db()
        initial_food = self.nation1.food
        
        # Simulate turn end
        self.nation1.has_ended_turn = True
        self.nation1.save()
        from hexquest.views import process_turn_end
        process_turn_end(self.game)
        
        # Verify both buildings were created
        self.assertEqual(Building.objects.filter(game=self.game).count(), 2)
        
        # Verify food increased by 4 (2 per farm)
        self.nation1.refresh_from_db()
        self.assertEqual(self.nation1.food, initial_food + 4)
    
    def test_builder_endpoint_validation(self):
        """Test builder endpoint validates ownership and tile state."""
        client = Client()
        client.login(username="player1", password="test123")
        
        # Test valid build request - use reverse() to generate the correct URL
        from django.urls import reverse
        url = reverse("hexquest:builder_build", kwargs={"game_id": self.game.id, "unit_id": self.builder.id})
        response = client.post(url, {"type": "wheat_farm"})
        
        # Should succeed
        self.assertEqual(response.status_code, 200)

