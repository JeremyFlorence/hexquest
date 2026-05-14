import uuid

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from hexquest.models import Game, HexTile, Nation, Unit
from hexquest.worldgen import generate_world
from project.hexgrid import hex_neighbors


class Command(BaseCommand):
    help = "Creates one generated test game with test nations and starting units."

    def add_arguments(self, parser):
        parser.add_argument(
            "--name",
            default="Test Game",
            help="Name of the test game.",
        )
        parser.add_argument(
            "--width",
            type=int,
            default=30,
            help="Map width in hexes.",
        )
        parser.add_argument(
            "--height",
            type=int,
            default=30,
            help="Map height in hexes.",
        )
        parser.add_argument(
            "--players",
            type=int,
            default=4,
            help="Number of test nations to create.",
        )
        parser.add_argument(
            "--seed",
            default=None,
            help="World generation seed. Randomly generated if omitted.",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing games before creating the test game.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        name = options["name"]
        width = options["width"]
        height = options["height"]
        player_count = options["players"]
        seed = options["seed"] or uuid.uuid4().hex[:12]
        reset = options["reset"]

        if reset:
            Game.objects.all().delete()

        game = Game.objects.create(
            name=name,
            width=width,
            height=height,
            seed=seed,
        )

        generate_world(
            game=game,
            width=width,
            height=height,
            seed=seed,
        )

        start_tiles = self.pick_start_tiles(game, player_count)

        colors = [
            "#ef4444",
            "#3b82f6",
            "#22c55e",
            "#eab308",
            "#a855f7",
            "#f97316",
            "#14b8a6",
            "#ec4899",
        ]

        for index, tile in enumerate(start_tiles):
            user, _ = User.objects.get_or_create(
                username=f"test_player_{index + 1}",
                defaults={
                    "email": f"test_player_{index + 1}@example.com",
                },
            )

            nation = Nation.objects.create(
                game=game,
                player=user,
                name=f"Nation {index + 1}",
                color=colors[index % len(colors)],
                food=10,
                gold=10,
                production=10,
            )

            self.assign_starting_area(nation, tile.q, tile.r)

            Unit.objects.create(
                game=game,
                nation=nation,
                q=tile.q,
                r=tile.r,
                unit_type="infantry",
                strength=10,
                movement=2,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Created game #{game.id}: {game.name} "
                f"({width}x{height}, seed={seed})"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"View it at: /games/{game.id}/map/"
            )
        )

    def pick_start_tiles(self, game, player_count):
        land_tiles = list(
            HexTile.objects.filter(game=game)
            .exclude(terrain__in=["water", "mountain"])
            .order_by("?")
        )

        if len(land_tiles) < player_count:
            raise ValueError("Not enough land tiles to place all players.")

        selected = []
        minimum_distance = max(4, min(game.width, game.height) // 4)

        for tile in land_tiles:
            if len(selected) >= player_count:
                break

            if all(
                self.hex_distance(tile.q, tile.r, other.q, other.r) >= minimum_distance
                for other in selected
            ):
                selected.append(tile)

        if len(selected) < player_count:
            selected = land_tiles[:player_count]

        return selected

    def assign_starting_area(self, nation, center_q, center_r):
        coords = [(center_q, center_r)]
        coords.extend(hex_neighbors(center_q, center_r))

        query = Q()
        for q, r in coords:
            query |= Q(q=q, r=r)

        HexTile.objects.filter(
            game=nation.game,
        ).filter(
            query,
        ).exclude(
            terrain__in=["water", "mountain"],
        ).update(
            owner=nation,
        )

    def hex_distance(self, aq, ar, bq, br):
        return (
            abs(aq - bq)
            + abs(aq + ar - bq - br)
            + abs(ar - br)
        ) // 2