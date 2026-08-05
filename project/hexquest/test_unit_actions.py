from django.test import TestCase, Client
from django.contrib.auth.models import User
from hexquest.models import Game, Nation, HexTile, Unit, Settlement

class UnitActionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testplayer", password="password")
        self.client = Client()
        self.client.login(username="testplayer", password="password")
        
        self.game = Game.objects.create(name="Test Game", width=10, height=10, seed="test")
        self.nation = Nation.objects.create(game=self.game, player=self.user, name="Test Nation", color="#ff0000")
        
        # Create some tiles
        self.tile_0_0 = HexTile.objects.create(game=self.game, q=0, r=0, terrain="plains")
        self.tile_1_0 = HexTile.objects.create(game=self.game, q=1, r=0, terrain="plains")
        
        # Create a unit
        self.unit = Unit.objects.create(
            game=self.game, 
            nation=self.nation, 
            q=0, 
            r=0, 
            unit_type="settler",
            movement=1
        )

    def test_move_unit(self):
        response = self.client.post(f"/games/{self.game.id}/unit/{self.unit.id}/move/", {
            "q": 1,
            "r": 0
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'queued')
        
        from hexquest.views import process_turn_end
        process_turn_end(self.game)

        self.unit.refresh_from_db()
        self.assertEqual(self.unit.q, 1)
        self.assertEqual(self.unit.r, 0)

    def test_settle_unit(self):
        # Move back to 0,0 if needed or just use current pos
        response = self.client.post(f"/games/{self.game.id}/unit/{self.unit.id}/settle/", {
            "name": "My New Settlement"
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'queued')

        from hexquest.views import process_turn_end
        process_turn_end(self.game)
        
        self.tile_0_0.refresh_from_db()
        self.assertEqual(self.tile_0_0.owner, self.nation)
        
        # Settler should be converted to builder at adjacent tile
        self.assertTrue(Unit.objects.filter(id=self.unit.id).exists())
        builder = Unit.objects.get(id=self.unit.id)
        self.assertEqual(builder.unit_type, 'builder')

        # Settlement should be created
        settlement = Settlement.objects.get(game=self.game, q=0, r=0, nation=self.nation)
        self.assertEqual(settlement.name, "My New Settlement")

    def test_rename_settlement(self):
        settlement = Settlement.objects.create(
            game=self.game,
            nation=self.nation,
            q=0,
            r=0,
            name="Old Name",
            tier="village"
        )
        response = self.client.post(f"/games/{self.game.id}/settlement/{settlement.id}/rename/", {
            "name": "New Name"
        })
        self.assertEqual(response.status_code, 200)
        settlement.refresh_from_db()
        self.assertEqual(settlement.name, "New Name")
