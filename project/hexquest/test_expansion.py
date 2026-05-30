from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from .models import Game, Nation, HexTile, Unit, Settlement
from .worldgen import generate_world

class SettlementExpansionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.client.force_login(self.user)
        
        self.game = Game.objects.create(name="Test Game", width=10, height=10, seed="test")
        self.nation = Nation.objects.create(
            game=self.game,
            player=self.user,
            name="Test Nation",
            color="#0000ff",
            gold=100
        )
        
    def test_worldgen_initial_territory(self):
        """Test that worldgen DOES NOT assign initial territory or settlements anymore."""
        generate_world(self.game, 10, 10, "test")
        
        # There should be exactly one nation in this test
        self.assertEqual(self.game.nations.count(), 1)
        nation = self.game.nations.first()
        
        # The nation should NOT own any tiles initially
        owned_tiles = HexTile.objects.filter(game=self.game, owner=nation)
        self.assertEqual(owned_tiles.count(), 0)
        
        # There should be NO settlement initially
        settlement = Settlement.objects.filter(game=self.game, nation=nation).first()
        self.assertIsNone(settlement)
        
        # But there should be a settler
        self.assertTrue(Unit.objects.filter(nation=nation, unit_type='settler').exists())

    def test_unit_settle_territory(self):
        """Test that building a settlement assigns adjacent tiles."""
        tile = HexTile.objects.create(game=self.game, q=0, r=0, terrain="plains")
        adj_tile = HexTile.objects.create(game=self.game, q=1, r=0, terrain="plains")
        unit = Unit.objects.create(game=self.game, nation=self.nation, q=0, r=0, unit_type="settler")
        
        self.client.post(reverse('hexquest:unit_settle', kwargs={'game_id': self.game.id, 'unit_id': unit.id}), {'name': 'New City'})
        
        tile.refresh_from_db()
        adj_tile.refresh_from_db()
        self.assertEqual(tile.owner, self.nation)
        self.assertEqual(adj_tile.owner, self.nation)

    def test_expand_settlement_success(self):
        """Test expanding settlement territory for gold."""
        settlement = Settlement.objects.create(game=self.game, nation=self.nation, q=0, r=0, name="Test Village")
        HexTile.objects.create(game=self.game, q=0, r=0, terrain="plains", owner=self.nation, settlement=settlement)
        target_tile = HexTile.objects.create(game=self.game, q=1, r=0, terrain="plains")
        
        initial_gold = self.nation.gold
        # Before expanding, nation owns 1 tile
        owned_count = HexTile.objects.filter(game=self.game, owner=self.nation).count()
        self.assertEqual(owned_count, 1)
        expected_cost = 10 + (owned_count * 5) # 10 + 5 = 15
        
        response = self.client.post(reverse('hexquest:expand_settlement', kwargs={
            'game_id': self.game.id, 
            'settlement_id': settlement.id
        }), {'q': 1, 'r': 0})
        
        self.assertEqual(response.status_code, 200)
        self.nation.refresh_from_db()
        self.assertEqual(self.nation.gold, initial_gold - expected_cost)
        
        target_tile.refresh_from_db()
        self.assertEqual(target_tile.owner, self.nation)
        self.assertEqual(target_tile.settlement, settlement)

    def test_unit_settle_settlement_association(self):
        """Test that building a settlement associates tiles with it."""
        tile = HexTile.objects.create(game=self.game, q=0, r=0, terrain="plains")
        adj_tile = HexTile.objects.create(game=self.game, q=1, r=0, terrain="plains")
        unit = Unit.objects.create(game=self.game, nation=self.nation, q=0, r=0, unit_type="settler")
        
        self.client.post(reverse('hexquest:unit_settle', kwargs={'game_id': self.game.id, 'unit_id': unit.id}), {'name': 'New City'})
        
        settlement = Settlement.objects.get(game=self.game, q=0, r=0)
        tile.refresh_from_db()
        adj_tile.refresh_from_db()
        
        self.assertEqual(tile.settlement, settlement)
        self.assertEqual(adj_tile.settlement, settlement)

    def test_expand_settlement_insufficient_gold(self):
        """Test expanding settlement fails if not enough gold."""
        self.nation.gold = 5
        self.nation.save()
        
        settlement = Settlement.objects.create(game=self.game, nation=self.nation, q=0, r=0, name="Test Village")
        HexTile.objects.create(game=self.game, q=0, r=0, terrain="plains", owner=self.nation, settlement=settlement)
        HexTile.objects.create(game=self.game, q=1, r=0, terrain="plains")
        
        response = self.client.post(reverse('hexquest:expand_settlement', kwargs={
            'game_id': self.game.id, 
            'settlement_id': settlement.id
        }), {'q': 1, 'r': 0})
        
        self.assertEqual(response.status_code, 400)
        self.assertIn("Not enough gold", response.json()['error'])
