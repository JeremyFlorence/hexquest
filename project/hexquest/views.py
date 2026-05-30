from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse
from django.utils.crypto import get_random_string

from .models import Game, HexTile, Nation, Unit, ChatMessage, Notification
from .worldgen import generate_world


def home(request):
    games = []

    if request.user.is_authenticated:
        games = (
            Game.objects
            .filter(nations__player=request.user)
            .distinct()
            .order_by("-created_at")
        )

    return render(
        request,
        "hexquest/home.html",
        {
            "games": games,
            "notifications": request.user.notifications.filter(is_read=False) if request.user.is_authenticated else [],
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
        creator=request.user,
        width=width,
        height=height,
        seed=seed,
        is_active=False,  # Use is_active=False to indicate it's in setup
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

    return redirect("hexquest:game_setup", game_id=game.id)


@login_required
def game_setup(request, game_id):
    game = get_object_or_404(Game, id=game_id)
    
    # Check if user is part of the game
    if not game.nations.filter(player=request.user).exists():
        return redirect("hexquest:home")

    if request.method == "POST":
        action = request.POST.get("action")
        is_creator = game.creator == request.user
        
        if action == "update_settings":
            if not is_creator:
                return redirect("hexquest:game_setup", game_id=game.id)
            game.name = request.POST.get("name", game.name)
            game.width = int(request.POST.get("width", game.width))
            game.height = int(request.POST.get("height", game.height))
            game.seed = request.POST.get("seed", game.seed)
            game.save()
            return redirect("hexquest:game_setup", game_id=game.id)
            
        elif action == "invite_player":
            if not is_creator:
                return redirect("hexquest:game_setup", game_id=game.id)
            username = request.POST.get("username")
            try:
                user_to_invite = User.objects.get(username=username)
                if not game.nations.filter(player=user_to_invite).exists():
                    # Check if already invited
                    if not Notification.objects.filter(user=user_to_invite, game=game, notification_type="game_invite").exists():
                        Notification.objects.create(
                            user=user_to_invite,
                            game=game,
                            notification_type="game_invite",
                            message=f"{request.user.username} invited you to join the game '{game.name}'"
                        )
            except User.DoesNotExist:
                pass # Ideally show an error message
            return redirect("hexquest:game_setup", game_id=game.id)

        elif action == "start_game":
            if not is_creator:
                return redirect("hexquest:game_setup", game_id=game.id)
            game.is_active = True
            game.save()
            generate_world(game, game.width, game.height, game.seed)
            return redirect("hexquest:game_map", game_id=game.id)

        elif action == "update_nation":
            nation = get_object_or_404(Nation, game=game, player=request.user)
            nation.name = request.POST.get("nation_name", nation.name)
            nation.color = request.POST.get("color", nation.color)
            nation.save()
            return redirect("hexquest:game_setup", game_id=game.id)

        elif action == "send_chat":
            text = request.POST.get("text")
            if text:
                ChatMessage.objects.create(
                    game=game,
                    user=request.user,
                    text=text
                )
            return redirect("hexquest:game_setup", game_id=game.id)

    users = User.objects.exclude(id__in=game.nations.values_list("player_id", flat=True))
    chat_messages = game.chat_messages.all().select_related("user")
    
    return render(
        request,
        "hexquest/game_setup.html",
        {
            "game": game,
            "nations": game.nations.all(),
            "available_users": users,
            "chat_messages": chat_messages,
        },
    )


def game_map(request, game_id):
    game = get_object_or_404(Game, id=game_id)

    hexes = (
        HexTile.objects
        .filter(game=game)
        .select_related("owner__player")
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


@login_required
def game_setup_updates(request, game_id):
    game = get_object_or_404(Game, id=game_id)
    if not game.nations.filter(player=request.user).exists():
        return JsonResponse({"error": "Unauthorized"}, status=403)

    last_chat_id = request.GET.get("last_chat_id")
    
    chat_qs = game.chat_messages.all()
    if last_chat_id:
        chat_qs = chat_qs.filter(id__gt=last_chat_id)
    
    messages = [
        {
            "id": msg.id,
            "user": msg.user.username,
            "text": msg.text,
            "created_at": msg.created_at.strftime("%H:%M"),
        }
        for msg in chat_qs
    ]
    
    nations = [
        {
            "player": n.player.username,
            "name": n.name,
            "color": n.color,
        }
        for n in game.nations.all()
    ]
    
    return JsonResponse({
        "messages": messages,
        "nations": nations,
        "game_active": game.is_active,
    })


@login_required
def accept_invite(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    game = notification.game
    
    if game and not game.nations.filter(player=request.user).exists():
        Nation.objects.create(
            game=game,
            player=request.user,
            name=f"{request.user.username}'s Nation",
            color="#f87171",
            food=10,
            gold=10,
            production=10,
        )
    
    notification.is_read = True
    notification.save()
    return redirect("hexquest:game_setup", game_id=game.id)


@login_required
def ignore_invite(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.save()
    return redirect("hexquest:home")
