import random

from django.db import models
from django.contrib.auth.models import User


class Game(models.Model):
    name = models.CharField(max_length=120)
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="created_games")
    current_turn = models.PositiveIntegerField(default=1)
    turn_timer = models.PositiveIntegerField(default=120)  # in seconds
    turn_end_time = models.DateTimeField(null=True, blank=True)
    active_nation = models.ForeignKey(
        "Nation",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    # Tracks whether any nation has acted during the current round (one pass
    # through all players), used to detect inactive games across rounds.
    round_activity_occurred = models.BooleanField(default=False)
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    seed = models.CharField(max_length=64)
    starting_gold = models.PositiveIntegerField(default=100)
    starting_food = models.PositiveIntegerField(default=20)
    starting_settlers = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    is_finished = models.BooleanField(default=False)
    is_abandoned = models.BooleanField(default=False)
    last_activity_turn = models.PositiveIntegerField(default=1)

    def __str__(self):
        return self.name


class Nation(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="nations")
    player = models.ForeignKey(User, on_delete=models.CASCADE, related_name="nations")
    name = models.CharField(max_length=120)
    color = models.CharField(max_length=20)
    food = models.IntegerField(default=0)
    gold = models.IntegerField(default=0)
    production = models.IntegerField(default=0)
    settlement_count = models.PositiveIntegerField(default=0)
    unit_count = models.PositiveIntegerField(default=0)
    has_ended_turn = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} ({self.game.name})"


class HexTile(models.Model):
    TERRAIN_CHOICES = [
        ("water", "Water"),
        ("plains", "Plains"),
        ("forest", "Forest"),
        ("hill", "Hill"),
        ("mountain", "Mountain"),
        ("desert", "Desert"),
    ]

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="hexes")
    q = models.IntegerField()
    r = models.IntegerField()
    terrain = models.CharField(max_length=20, choices=TERRAIN_CHOICES)
    owner = models.ForeignKey(
        "Nation",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="hexes",
    )
    settlement = models.ForeignKey(
        "Settlement",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="hexes",
    )

    class Meta:
        unique_together = ("game", "q", "r")
        indexes = [
            models.Index(fields=["game", "q", "r"]),
            models.Index(fields=["game", "owner"]),
        ]

    def __str__(self):
        return f"Hex ({self.q}, {self.r}) - {self.game.name}"


class Unit(models.Model):
    UNIT_TYPES = [
        ("infantry", "Infantry"),
        ("cavalry", "Cavalry"),
        ("settler", "Settler"),
        ("builder", "Builder"),
        ("spearman", "Spearman"),
        ("swordsman", "Swordsman"),
    ]

    # Base combat/survival stats assigned to a unit when it's created.
    UNIT_STATS = {
        "settler": {"hitpoints": 100, "attack": 1, "defense": 1},
        "builder": {"hitpoints": 100, "attack": 1, "defense": 1},
        "infantry": {"hitpoints": 100, "attack": 1, "defense": 1},
        "cavalry": {"hitpoints": 100, "attack": 1, "defense": 1},
        "spearman": {"hitpoints": 1000, "attack": 8, "defense": 10},
        "swordsman": {"hitpoints": 1000, "attack": 10, "defense": 8},
    }

    # Combat units that can be trained at a Barracks and issue an Attack order.
    COMBAT_UNIT_TYPES = {"spearman", "swordsman"}

    RECRUIT_COSTS = {
        "spearman": 20,
        "swordsman": 20,
    }

    # Scales a unit's attack/defense stat into an actual hit's damage. Chosen
    # so a duel between two full-health combat units (1000 HP, attack/defense
    # ~8-10) typically ends in about 3-4 exchanges rather than dozens.
    DAMAGE_SCALE = 30
    # Each hit's damage is randomized by +/- this fraction of its scaled value.
    DAMAGE_VARIANCE = 0.15

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="units")
    nation = models.ForeignKey(Nation, on_delete=models.CASCADE, related_name="units")
    q = models.IntegerField()
    r = models.IntegerField()
    unit_type = models.CharField(max_length=20, choices=UNIT_TYPES)
    strength = models.IntegerField(default=10)
    movement = models.IntegerField(default=2)
    hitpoints = models.IntegerField(default=100)
    attack = models.IntegerField(default=1)
    defense = models.IntegerField(default=1)
    last_action_turn = models.PositiveIntegerField(default=0)
    queued_action = models.JSONField(null=True, blank=True)

    @classmethod
    def stats_for(cls, unit_type):
        return cls.UNIT_STATS.get(unit_type, {"hitpoints": 100, "attack": 1, "defense": 1})

    @classmethod
    def roll_damage(cls, stat):
        """Randomized damage for one attack or counter-attack, derived from
        an attack/defense stat via DAMAGE_SCALE and jittered by DAMAGE_VARIANCE."""
        variance = random.uniform(1 - cls.DAMAGE_VARIANCE, 1 + cls.DAMAGE_VARIANCE)
        return max(1, round(stat * cls.DAMAGE_SCALE * variance))

    @property
    def max_hitpoints(self):
        return self.stats_for(self.unit_type)["hitpoints"]

    def __str__(self):
        return f"{self.get_unit_type_display()} - {self.nation.name} ({self.q}, {self.r})"


class Settlement(models.Model):
    TIERS = [
        ("village", "Village"),
        ("town", "Town"),
        ("city", "City"),
    ]

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="settlements")
    nation = models.ForeignKey(Nation, on_delete=models.CASCADE, related_name="settlements")
    q = models.IntegerField()
    r = models.IntegerField()
    name = models.CharField(max_length=120)
    tier = models.CharField(max_length=20, choices=TIERS, default="village")
    population = models.PositiveIntegerField(default=1)
    last_action_turn = models.PositiveIntegerField(default=0)
    queued_action = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.get_tier_display()}) - {self.nation.name}"

    class Meta:
        unique_together = ("game", "q", "r")


class ChatMessage(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="chat_messages")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}: {self.text[:20]}{'...' if len(self.text) > 20 else ''}"

    class Meta:
        ordering = ["created_at"]


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ("game_invite", "Game Invitation"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    message = models.TextField()
    game = models.ForeignKey(Game, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.get_notification_type_display()} for {self.user.username}"

    class Meta:
        ordering = ["-created_at"]


class Building(models.Model):
    BUILDING_TYPES = [
        ("wheat_farm", "Wheat Farm"),
        ("barracks", "Barracks"),
    ]

    BUILDING_COSTS = {
        "wheat_farm": 10,
        "barracks": 15,
    }

    # Terrain a building type may be constructed on; omitted types allow any
    # non-water tile.
    BUILDING_TERRAIN = {
        "wheat_farm": {"plains"},
    }

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="buildings")
    hex_tile = models.OneToOneField(HexTile, on_delete=models.CASCADE, related_name="building")
    building_type = models.CharField(max_length=20, choices=BUILDING_TYPES)
    queued_action = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_building_type_display()} at ({self.hex_tile.q}, {self.hex_tile.r})"


class Friendship(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="friendships")
    friend = models.ForeignKey(User, on_delete=models.CASCADE, related_name="friend_of")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "friend")

    def __str__(self):
        return f"{self.user.username} is friends with {self.friend.username}"
