from django.test import TestCase, Client
from django.contrib.auth.models import User
from hexquest.models import Game, Nation, HexTile, Unit, Settlement
from hexquest.views import process_turn_end
from django.utils import timezone
import datetime

class QueuedActionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testplayer", password="password")
        self.client = Client()
        self.client.login(username="testplayer", password="password")
        
        self.game = Game.objects.create(name="Test Game", width=10, height=10, seed="test")
        self.nation = Nation.objects.create(
            game=self.game, 
            player=self.user, 
            name="Test Nation", 
            color="#ff0000",
            gold=100
        )
        
        # Create some tiles
        self.tile_0_0 = HexTile.objects.create(game=self.game, q=0, r=0, terrain="plains")
        self.tile_1_0 = HexTile.objects.create(game=self.game, q=1, r=0, terrain="plains")
        self.tile_2_0 = HexTile.objects.create(game=self.game, q=2, r=0, terrain="plains")
        self.tile_1_1 = HexTile.objects.create(game=self.game, q=1, r=1, terrain="plains")
        
        # Create a unit
        self.unit = Unit.objects.create(
            game=self.game, 
            nation=self.nation, 
            q=0, 
            r=0, 
            unit_type="settler",
            movement=1
        )

    def test_queue_unit_move(self):
        # First action: move to 1,0
        self.client.post(f"/games/{self.game.id}/unit/{self.unit.id}/move/", {"q": 1, "r": 0})
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.q, 1)
        self.assertEqual(self.unit.last_action_turn, self.game.current_turn)

        # Second action: queue move to 2,0
        response = self.client.post(f"/games/{self.game.id}/unit/{self.unit.id}/move/", {"q": 2, "r": 0})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'queued')
        
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.queued_action, {"type": "move", "q": 2, "r": 0})
        self.assertEqual(self.unit.q, 1) # Still at 1,0

        # End turn
        process_turn_end(self.game)
        
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.q, 2)
        self.assertIsNone(self.unit.queued_action)

    def test_queue_unit_settle(self):
        # First action: move to 1,0
        self.client.post(f"/games/{self.game.id}/unit/{self.unit.id}/move/", {"q": 1, "r": 0})
        
        # Second action: queue settle
        response = self.client.post(f"/games/{self.game.id}/unit/{self.unit.id}/settle/", {"name": "New City"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'queued')
        
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.queued_action, {"type": "settle", "name": "New City"})

        # End turn
        process_turn_end(self.game)
        
        # Unit should be gone, settlement should exist
        self.assertFalse(Unit.objects.filter(id=self.unit.id).exists())
        self.assertTrue(Settlement.objects.filter(game=self.game, q=1, r=0).exists())

    def test_queue_settlement_upgrade(self):
        settlement = Settlement.objects.create(
            game=self.game, nation=self.nation, q=0, r=0, name="Base", tier="village", population=5
        )
        self.tile_0_0.owner = self.nation
        self.tile_0_0.settlement = settlement
        self.tile_0_0.save()

        # First action: expand (not really needed but let's say it acted)
        settlement.last_action_turn = self.game.current_turn
        settlement.save()

        # Queue upgrade
        response = self.client.post(f"/games/{self.game.id}/settlement/{settlement.id}/upgrade/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'queued')

        # End turn
        process_turn_end(self.game)
        
        settlement.refresh_from_db()
        self.assertEqual(settlement.tier, "town")

    def test_queue_settlement_expand(self):
        settlement = Settlement.objects.create(
            game=self.game, nation=self.nation, q=0, r=0, name="Base", tier="village"
        )
        self.tile_0_0.owner = self.nation
        self.tile_0_0.settlement = settlement
        self.tile_0_0.save()

        # Set acted
        settlement.last_action_turn = self.game.current_turn
        settlement.save()

        # Queue expand to 1,0
        response = self.client.post(f"/games/{self.game.id}/settlement/{settlement.id}/expand/", {"q": 1, "r": 0})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'queued')

        # End turn
        process_turn_end(self.game)
        
        self.tile_1_0.refresh_from_db()
        self.assertEqual(self.tile_1_0.owner, self.nation)
        self.assertEqual(self.tile_1_0.settlement, settlement)

    def test_queue_invalid_move(self):
        # 1,1 was already created in setUp
        mountain_tile = self.tile_1_1
        mountain_tile.terrain = "mountain"
        mountain_tile.save()
        
        # Set acted
        self.unit.last_action_turn = self.game.current_turn
        self.unit.save()
        
        # Queue move to mountain (invalid)
        self.client.post(f"/games/{self.game.id}/unit/{self.unit.id}/move/", {"q": 1, "r": 1})
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.queued_action, {"type": "move", "q": 1, "r": 1})
        
        # Change mountain to water just to be sure it's invalid
        mountain_tile.terrain = "water"
        mountain_tile.save()
        
        # End turn
        process_turn_end(self.game)
        
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.q, 0) # Should not have moved
        self.assertIsNone(self.unit.queued_action) # Should have been cleared anyway
