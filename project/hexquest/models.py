from django.db import models
from django.contrib.auth.models import User


class Game(models.Model):
    name = models.CharField(max_length=120)
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="created_games")
    current_turn = models.PositiveIntegerField(default=1)
    turn_timer = models.PositiveIntegerField(default=120)  # in seconds
    turn_end_time = models.DateTimeField(null=True, blank=True)
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    seed = models.CharField(max_length=64)
    starting_gold = models.PositiveIntegerField(default=100)
    starting_food = models.PositiveIntegerField(default=20)
    starting_settlers = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)


class Nation(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="nations")
    player = models.ForeignKey(User, on_delete=models.CASCADE, related_name="nations")
    name = models.CharField(max_length=120)
    color = models.CharField(max_length=20)
    food = models.IntegerField(default=0)
    gold = models.IntegerField(default=0)
    production = models.IntegerField(default=0)
    has_ended_turn = models.BooleanField(default=False)


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


class Unit(models.Model):
    UNIT_TYPES = [
        ("infantry", "Infantry"),
        ("cavalry", "Cavalry"),
        ("settler", "Settler"),
    ]

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="units")
    nation = models.ForeignKey(Nation, on_delete=models.CASCADE, related_name="units")
    q = models.IntegerField()
    r = models.IntegerField()
    unit_type = models.CharField(max_length=20, choices=UNIT_TYPES)
    strength = models.IntegerField(default=10)
    movement = models.IntegerField(default=2)


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

    class Meta:
        unique_together = ("game", "q", "r")


class ChatMessage(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="chat_messages")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

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

    class Meta:
        ordering = ["-created_at"]
