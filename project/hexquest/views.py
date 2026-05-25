from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.crypto import get_random_string

from .models import Game, HexTile, Nation, Unit
from .worldgen import generate_world


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
def home(request):
    games = []

    if request.user.is_authenticated:
        games = (
            Game.objects
            .filter(nations__player=request.user, is_active=True)
            .distinct()
            .order_by("-created_at")
        )

    return render(
        request,
        "hexquest/home.html",
        {
            "games": games,
        },
    )


def register(request):
    if request.user.is_authenticated:
        return redirect("hexquest:home")

    if request.method == "POST":
        form = UserCreationForm(request.POST)

        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("hexquest:home")
    else:
        form = UserCreationForm()

    return render(
        request,
        "hexquest/register.html",
        {
            "form": form,
        },
    )


@login_required
def create_game(request):
    game_number = Game.objects.count() + 1
    seed = get_random_string(16)
    width = 16
    height = 12

    game = Game.objects.create(
        name=f"{request.user.username}'s Game {game_number}",
        width=width,
        height=height,
        seed=seed,
    )

    Nation.objects.create(
        game=game,
        player=request.user,
        name=f"{request.user.username}'s Nation",
        color="#38bdf8",
        food=10,
        gold=10,
        production=10,
    )

    generate_world(game, width, height, seed)

    return redirect("hexquest:game_map", game_id=game.id)


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
