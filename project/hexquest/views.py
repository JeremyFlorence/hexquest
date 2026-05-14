from django.shortcuts import get_object_or_404, render

from .models import Game, HexTile, Unit


def game_map(request, game_id):
    game = get_object_or_404(Game, id=game_id)

    hexes = (
        HexTile.objects
        .filter(game=game)
        .select_related("owner")
        .order_by("r", "q")
    )

    units = (
        Unit.objects
        .filter(game=game)
        .select_related("nation")
    )

    units_by_position = {
        f"{unit.q},{unit.r}": unit
        for unit in units
    }

    return render(
        request,
        "hexquest/game_map.html",
        {
            "game": game,
            "hexes": hexes,
            "units_by_position": units_by_position,
        },
    )
