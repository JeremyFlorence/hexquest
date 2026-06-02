from django.test import TestCase, Client
from django.contrib.auth.models import User
from hexquest.models import Game, Nation, HexTile, Unit, Settlement

class ActionRestrictionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testplayer", password="password")
        self.client = Client()
        self.client.login(username="testplayer", password="password")
        
        self.game = Game.objects.create(name="Test Game", width=10, height=10, seed="test")
        self.nation = Nation.objects.create(game=self.game, player=self.user, name="Test Nation", color="#ff0000", gold=1000)
        
        # Create some tiles
        self.tile_0_0 = HexTile.objects.create(game=self.game, q=0, r=0, terrain="plains")
        self.tile_1_0 = HexTile.objects.create(game=self.game, q=1, r=0, terrain="plains")
        self.tile_2_0 = HexTile.objects.create(game=self.game, q=2, r=0, terrain="plains")
        self.tile_0_1 = HexTile.objects.create(game=self.game, q=0, r=1, terrain="plains")
        
        # Create a unit
        self.unit = Unit.objects.create(
            game=self.game, 
            nation=self.nation, 
            q=0, 
            r=0, 
            unit_type="settler",
            movement=2
        )

    def test_unit_cannot_move_twice_in_one_turn(self):
        # First move
        response = self.client.post(f"/games/{self.game.id}/unit/{self.unit.id}/move/", {
            "q": 1, "r": 0
        })
        self.assertEqual(response.status_code, 200)
        
        # Second move in same turn
        response = self.client.post(f"/games/{self.game.id}/unit/{self.unit.id}/move/", {
            "q": 2, "r": 0
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("already acted", response.json()["error"])
        
        # Advance turn
        from hexquest.views import process_turn_end
        process_turn_end(self.game)
        
        # Should be able to move now
        response = self.client.post(f"/games/{self.game.id}/unit/{self.unit.id}/move/", {
            "q": 2, "r": 0
        })
        self.assertEqual(response.status_code, 200)

    def test_unit_cannot_settle_after_moving(self):
        # Move unit
        self.client.post(f"/games/{self.game.id}/unit/{self.unit.id}/move/", {
            "q": 1, "r": 0
        })
        
        # Try to settle in same turn
        response = self.client.post(f"/games/{self.game.id}/unit/{self.unit.id}/settle/", {
            "name": "New City"
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("already acted", response.json()["error"])

    def test_settlement_cannot_upgrade_twice_in_one_turn(self):
        settlement = Settlement.objects.create(
            game=self.game, nation=self.nation, q=0, r=0, name="Base", population=20
        )
        # First upgrade
        response = self.client.post(f"/games/{self.game.id}/settlement/{settlement.id}/upgrade/")
        self.assertEqual(response.status_code, 200)
        
        # Second upgrade
        response = self.client.post(f"/games/{self.game.id}/settlement/{settlement.id}/upgrade/")
        self.assertEqual(response.status_code, 400)
        self.assertIn("already acted", response.json()["error"])

    def test_settlement_cannot_expand_twice_in_one_turn(self):
        settlement = Settlement.objects.create(
            game=self.game, nation=self.nation, q=0, r=0, name="Base"
        )
        self.tile_0_0.owner = self.nation
        self.tile_0_0.settlement = settlement
        self.tile_0_0.save()
        
        # First expand
        response = self.client.post(f"/games/{self.game.id}/settlement/{settlement.id}/expand/", {
            "q": 1, "r": 0
        })
        self.assertEqual(response.status_code, 200)
        
        # Second expand
        response = self.client.post(f"/games/{self.game.id}/settlement/{settlement.id}/expand/", {
            "q": 0, "r": 1
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("already acted", response.json()["error"])

    def test_settlement_cannot_upgrade_and_expand_in_same_turn(self):
        settlement = Settlement.objects.create(
            game=self.game, nation=self.nation, q=0, r=0, name="Base", population=10
        )
        self.tile_0_0.owner = self.nation
        self.tile_0_0.settlement = settlement
        self.tile_0_0.save()

        # Upgrade
        self.client.post(f"/games/{self.game.id}/settlement/{settlement.id}/upgrade/")
        
        # Try expand
        response = self.client.post(f"/games/{self.game.id}/settlement/{settlement.id}/expand/", {
            "q": 1, "r": 0
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("already acted", response.json()["error"])
