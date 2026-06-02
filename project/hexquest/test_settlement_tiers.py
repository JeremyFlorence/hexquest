from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from .models import Game, Nation, HexTile, Unit, Settlement

class SettlementTierTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.client.force_login(self.user)
        
        self.game = Game.objects.create(name="Test Game", width=10, height=10)
        self.nation = Nation.objects.create(
            game=self.game,
            player=self.user,
            name="Test Nation",
            color="#0000ff"
        )
        self.tile = HexTile.objects.create(game=self.game, q=0, r=0, terrain="plains")
        self.unit = Unit.objects.create(
            game=self.game,
            nation=self.nation,
            q=0,
            r=0,
            unit_type="settler"
        )

    def test_initial_settlement_is_village(self):
        """Test that a new settlement starts as a Village."""
        self.client.post(reverse('hexquest:unit_settle', kwargs={'game_id': self.game.id, 'unit_id': self.unit.id}), {'name': 'New City'})
        
        from .views import process_turn_end
        process_turn_end(self.game)

        settlement = Settlement.objects.get(game=self.game, q=0, r=0)
        self.assertEqual(settlement.tier, "village")
        self.assertEqual(settlement.population, 1)

    def test_upgrade_to_town_failure_insufficient_pop(self):
        """Test that upgrading to Town fails if population is too low."""
        settlement = Settlement.objects.create(
            game=self.game, nation=self.nation, q=0, r=0, name="Test Village", tier="village", population=4
        )
        
        response = self.client.post(reverse('hexquest:upgrade_settlement', kwargs={'game_id': self.game.id, 'settlement_id': settlement.id}))
        self.assertEqual(response.status_code, 400)
        self.assertIn("Need at least 5 population", response.json()['error'])
        
        settlement.refresh_from_db()
        self.assertEqual(settlement.tier, "village")

    def test_upgrade_to_town_success(self):
        """Test successful upgrade to Town."""
        settlement = Settlement.objects.create(
            game=self.game, nation=self.nation, q=0, r=0, name="Test Village", tier="village", population=5
        )
        
        response = self.client.post(reverse('hexquest:upgrade_settlement', kwargs={'game_id': self.game.id, 'settlement_id': settlement.id}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'queued')
        
        from .views import process_turn_end
        process_turn_end(self.game)

        settlement.refresh_from_db()
        self.assertEqual(settlement.tier, "town")

    def test_upgrade_to_city_failure_insufficient_pop(self):
        """Test that upgrading to City fails if population is too low."""
        settlement = Settlement.objects.create(
            game=self.game, nation=self.nation, q=0, r=0, name="Test Town", tier="town", population=14
        )
        
        response = self.client.post(reverse('hexquest:upgrade_settlement', kwargs={'game_id': self.game.id, 'settlement_id': settlement.id}))
        self.assertEqual(response.status_code, 400)
        self.assertIn("Need at least 15 population", response.json()['error'])
        
        settlement.refresh_from_db()
        self.assertEqual(settlement.tier, "town")

    def test_upgrade_to_city_success(self):
        """Test successful upgrade to City."""
        settlement = Settlement.objects.create(
            game=self.game, nation=self.nation, q=0, r=0, name="Test Town", tier="town", population=15
        )
        
        response = self.client.post(reverse('hexquest:upgrade_settlement', kwargs={'game_id': self.game.id, 'settlement_id': settlement.id}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'queued')
        
        from .views import process_turn_end
        process_turn_end(self.game)

        settlement.refresh_from_db()
        self.assertEqual(settlement.tier, "city")
