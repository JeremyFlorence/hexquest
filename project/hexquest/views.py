import json
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse, HttpResponseForbidden
from django.db import transaction
from django.utils.crypto import get_random_string
from django.utils import timezone
import datetime

from .models import Game, HexTile, Nation, Unit, ChatMessage, Notification, Settlement, Friendship
from .worldgen import generate_world
from project.hexgrid import hex_distance


def home(request):
    if request.GET.get("abandoned"):
        messages.warning(request, "The game creator has abandoned the game.")

    games = []

    if request.user.is_authenticated:
        games = (
            Game.objects
            .filter(nations__player=request.user, is_finished=False)
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


@login_required
def game_history(request):
    games = (
        Game.objects
        .filter(nations__player=request.user, is_finished=True)
        .prefetch_related('nations', 'units', 'settlements')
        .distinct()
        .order_by("-created_at")
    )
    return render(request, "hexquest/game_history.html", {"games": games})


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
        food=game.starting_food,
        gold=game.starting_gold,
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
            game.turn_timer = int(request.POST.get("turn_timer", game.turn_timer))
            game.starting_gold = int(request.POST.get("starting_gold", game.starting_gold))
            game.starting_food = int(request.POST.get("starting_food", game.starting_food))
            game.starting_settlers = int(request.POST.get("starting_settlers", game.starting_settlers))
            game.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({"status": "ok"})
            return redirect("hexquest:game_setup", game_id=game.id)
            
        elif action == "invite_player":
            if not is_creator:
                return redirect("hexquest:game_setup", game_id=game.id)
            username = request.POST.get("username")
            try:
                user_to_invite = User.objects.get(username=username)
                # Check if user is a friend
                if Friendship.objects.filter(user=request.user, friend=user_to_invite).exists():
                    if not game.nations.filter(player=user_to_invite).exists():
                        # Check if already invited
                        if not Notification.objects.filter(user=user_to_invite, game=game, notification_type="game_invite").exists():
                            Notification.objects.create(
                                user=user_to_invite,
                                game=game,
                                notification_type="game_invite",
                                message=f"{request.user.username} invited you to join the game '{game.name}'"
                            )
                else:
                    messages.error(request, "You can only invite users who are on your friends list.")
            except User.DoesNotExist:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({"status": "error", "message": "User does not exist"}, status=404)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({"status": "ok"})
            return redirect("hexquest:game_setup", game_id=game.id)

        elif action == "start_game":
            if not is_creator:
                return redirect("hexquest:game_setup", game_id=game.id)
            game.is_active = True
            from django.utils import timezone
            import datetime
            game.turn_end_time = timezone.now() + datetime.timedelta(seconds=game.turn_timer)
            game.save()
            generate_world(game, game.width, game.height, game.seed)
            return redirect("hexquest:game_map", game_id=game.id)

        elif action == "abandon_game":
            if not is_creator:
                return redirect("hexquest:game_setup", game_id=game.id)
            game.is_abandoned = True
            game.save()
            game.delete()
            messages.success(request, "Game abandoned and deleted.")
            return redirect("hexquest:home")

        elif action == "update_nation":
            nation = get_object_or_404(Nation, game=game, player=request.user)
            nation.name = request.POST.get("nation_name", nation.name)
            nation.color = request.POST.get("color", nation.color)
            nation.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({"status": "ok"})
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

    friend_ids = Friendship.objects.filter(user=request.user).values_list("friend_id", flat=True)
    users = User.objects.filter(id__in=friend_ids).exclude(id__in=game.nations.values_list("player_id", flat=True))
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


@login_required
def game_map(request, game_id):
    game = get_object_or_404(Game, id=game_id)
    if game.is_finished:
        return redirect("hexquest:game_history")
    nation = get_object_or_404(Nation, game=game, player=request.user)

    remaining_time = 0
    if game.turn_end_time:
        remaining_time = max(0, int((game.turn_end_time - timezone.now()).total_seconds()))

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "end_turn":
            nation.has_ended_turn = True
            nation.save()
            
            # Check if all nations have ended their turn
            if not game.nations.filter(has_ended_turn=False).exists():
                process_turn_end(game)
            
            return redirect("hexquest:game_map", game_id=game.id)

    # Check if timer has expired
    if game.turn_end_time and timezone.now() >= game.turn_end_time:
        process_turn_end(game)
        # Reload game after turn processing
        game.refresh_from_db()

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
            "nation": nation,
            "remaining_time": int((game.turn_end_time - timezone.now()).total_seconds()) if game.turn_end_time else 0
        },
    )


def process_turn_end(game):
    if game.is_finished:
        return

    # Check for activity in this turn
    activity_occurred = False

    # Process queued actions for units
    units_with_queued = list(game.units.exclude(queued_action__isnull=True))
    for unit in units_with_queued:
        activity_occurred = True
        action = unit.queued_action
        unit.queued_action = None
        
        if action['type'] == 'move':
            q, r = action['q'], action['r']
            if hex_distance(unit.q, unit.r, q, r) <= unit.movement:
                target_tile = HexTile.objects.filter(game=game, q=q, r=r).first()
                if target_tile and target_tile.terrain != "water":
                    unit.q = q
                    unit.r = r
                    unit.last_action_turn = game.current_turn
        
        elif action['type'] == 'settle':
            name = action['name']
            tile = HexTile.objects.filter(game=game, q=unit.q, r=unit.r).first()
            if tile and not tile.owner and unit.unit_type == 'settler':
                with transaction.atomic():
                    settlement = Settlement.objects.create(
                        game=game,
                        nation=unit.nation,
                        q=unit.q,
                        r=unit.r,
                        name=name,
                        tier="village",
                        population=1,
                        last_action_turn=game.current_turn
                    )
                    tile.owner = unit.nation
                    tile.settlement = settlement
                    tile.save()
                    from project.hexgrid import hex_neighbors
                    for n_q, n_r in hex_neighbors(tile.q, tile.r):
                        adj_tile = HexTile.objects.filter(game=game, q=n_q, r=n_r).first()
                        if adj_tile and not adj_tile.owner and adj_tile.terrain != "water":
                            adj_tile.owner = unit.nation
                            adj_tile.settlement = settlement
                            adj_tile.save()
                    unit.delete()
                    continue # Unit deleted, don't save
        unit.save()

    # Process queued actions for settlements
    settlements_with_queued = list(game.settlements.exclude(queued_action__isnull=True))
    for settlement in settlements_with_queued:
        activity_occurred = True
        action = settlement.queued_action
        settlement.queued_action = None
        
        if action['type'] == 'upgrade':
            if settlement.tier == "village" and settlement.population >= 5:
                settlement.tier = "town"
                settlement.last_action_turn = game.current_turn
            elif settlement.tier == "town" and settlement.population >= 15:
                settlement.tier = "city"
                settlement.last_action_turn = game.current_turn
        
        elif action['type'] == 'expand':
            q, r = action['q'], action['r']
            target_tile = HexTile.objects.filter(game=game, q=q, r=r).first()
            if target_tile and not target_tile.owner and target_tile.terrain != "water":
                is_adjacent = False
                owned_tiles = HexTile.objects.filter(game=game, settlement=settlement)
                for tile in owned_tiles:
                    if hex_distance(tile.q, tile.r, q, r) == 1:
                        is_adjacent = True
                        break
                if is_adjacent:
                    owned_tiles_count = HexTile.objects.filter(game=game, owner=settlement.nation).count()
                    cost = 10 + (owned_tiles_count * 5)
                    if settlement.nation.gold >= cost:
                        with transaction.atomic():
                            settlement.nation.gold -= cost
                            settlement.nation.save()
                            target_tile.owner = settlement.nation
                            target_tile.settlement = settlement
                            target_tile.save()
                            settlement.last_action_turn = game.current_turn
        settlement.save()

    if activity_occurred:
        game.last_activity_turn = game.current_turn
        game.save()

    # Check for game end condition (3 turns without activity)
    if game.current_turn - game.last_activity_turn >= 3:
        game.is_finished = True
        # Save statistics and delete temporary game objects
        for nation in game.nations.all():
            nation.settlement_count = nation.settlements.count()
            nation.unit_count = nation.units.count()
            nation.save()
        
        game.hexes.all().delete()
        game.settlements.all().delete()
        game.units.all().delete()

    game.current_turn += 1
    game.turn_end_time = timezone.now() + datetime.timedelta(seconds=game.turn_timer)
    game.save()
    
    # Reset all nations' end turn status
    game.nations.all().update(has_ended_turn=False)


@login_required
def game_updates(request, game_id):
    game = get_object_or_404(Game, id=game_id)
    nation = get_object_or_404(Nation, game=game, player=request.user)
    
    # Check if timer has expired
    if game.turn_end_time and timezone.now() >= game.turn_end_time:
        process_turn_end(game)
        game.refresh_from_db()

    remaining_time = int((game.turn_end_time - timezone.now()).total_seconds()) if game.turn_end_time else 0
    
    return JsonResponse({
        "current_turn": game.current_turn,
        "remaining_time": max(0, remaining_time),
        "has_ended_turn": nation.has_ended_turn,
        "gold": nation.gold,
        "food": nation.food,
        "unit_count": nation.units.count(),
        "queued_actions": [
            {
                "id": u.id,
                "type": "unit",
                "unit_type": u.unit_type,
                "action": u.queued_action,
                "q": u.q,
                "r": u.r
            } for u in nation.units.exclude(queued_action__isnull=True)
        ] + [
            {
                "id": s.id,
                "type": "settlement",
                "name": s.name,
                "action": s.queued_action,
                "q": s.q,
                "r": s.r
            } for s in nation.settlements.exclude(queued_action__isnull=True)
        ]
    })


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
        "settings": {
            "name": game.name,
            "width": game.width,
            "height": game.height,
            "seed": game.seed,
            "turn_timer": game.turn_timer,
            "starting_gold": game.starting_gold,
            "starting_food": game.starting_food,
            "starting_settlers": game.starting_settlers,
        }
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
            food=game.starting_food,
            gold=game.starting_gold,
            production=10,
        )
    
    notification.is_read = True
    notification.save()
    return redirect("hexquest:game_setup", game_id=game.id)


@login_required
def unit_move(request, game_id, unit_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    unit = get_object_or_404(Unit, id=unit_id, game_id=game_id)
    if unit.nation.player != request.user:
        return HttpResponseForbidden("You do not own this unit")

    if unit.nation.has_ended_turn:
        return JsonResponse({"error": "You have already ended your turn"}, status=400)

    if unit.queued_action:
        return JsonResponse({"error": "This unit has already acted this turn"}, status=400)

    try:
        q = int(request.POST.get("q"))
        r = int(request.POST.get("r"))
    except (TypeError, ValueError):
        return JsonResponse({"error": "Invalid coordinates"}, status=400)

    # Check distance
    if hex_distance(unit.q, unit.r, q, r) > unit.movement:
        return JsonResponse({"error": "Too far to move"}, status=400)

    # Check if tile exists and is not water
    target_tile = HexTile.objects.filter(game_id=game_id, q=q, r=r).first()
    if not target_tile or target_tile.terrain == "water":
        return JsonResponse({"error": "Cannot move there"}, status=400)

    unit.queued_action = {"type": "move", "q": q, "r": r}
    unit.save()
    return JsonResponse({"status": "queued", "message": "Action queued for next turn"})


@login_required
def unit_settle(request, game_id, unit_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    unit = get_object_or_404(Unit, id=unit_id, game_id=game_id)
    if unit.nation.player != request.user:
        return HttpResponseForbidden("You do not own this unit")

    if unit.nation.has_ended_turn:
        return JsonResponse({"error": "You have already ended your turn"}, status=400)

    if unit.queued_action:
        return JsonResponse({"error": "This unit has already acted this turn"}, status=400)

    if unit.unit_type != "settler":
        return JsonResponse({"error": "Only settlers can build settlements"}, status=400)

    name = request.POST.get("name")
    if not name:
        return JsonResponse({"error": "Settlement name is required"}, status=400)

    tile = HexTile.objects.filter(game_id=game_id, q=unit.q, r=unit.r).first()
    if not tile:
        return JsonResponse({"error": "Tile not found"}, status=404)

    if tile.owner:
        return JsonResponse({"error": "Tile already owned"}, status=400)

    unit.queued_action = {"type": "settle", "name": name}
    unit.save()
    return JsonResponse({"status": "queued", "message": "Action queued for next turn"})


@login_required
def rename_settlement(request, game_id, settlement_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    settlement = get_object_or_404(Settlement, id=settlement_id, game_id=game_id)
    if settlement.nation.player != request.user:
        return HttpResponseForbidden("You do not own this settlement")

    name = request.POST.get("name")
    if not name or not name.strip():
        return JsonResponse({"error": "Settlement name cannot be empty"}, status=400)

    settlement.name = name.strip()
    settlement.save()

    return JsonResponse({"status": "ok", "name": settlement.name})


def ignore_invite(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.save()
    return redirect("hexquest:home")


@login_required
def upgrade_settlement(request, game_id, settlement_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    settlement = get_object_or_404(Settlement, id=settlement_id, game_id=game_id)
    if settlement.nation.player != request.user:
        return HttpResponseForbidden("You do not own this settlement")

    if settlement.nation.has_ended_turn:
        return JsonResponse({"error": "You have already ended your turn"}, status=400)

    if settlement.queued_action:
        return JsonResponse({"error": "This settlement has already acted this turn"}, status=400)

    # Upgrade logic validation
    if settlement.tier == "village":
        if settlement.population < 5:
            return JsonResponse({"error": "Need at least 5 population to upgrade to Town"}, status=400)
    elif settlement.tier == "town":
        if settlement.population < 15:
            return JsonResponse({"error": "Need at least 15 population to upgrade to City"}, status=400)
    else:
        return JsonResponse({"error": "Settlement is already at maximum tier"}, status=400)

    settlement.queued_action = {"type": "upgrade"}
    settlement.save()
    return JsonResponse({"status": "queued", "message": "Action queued for next turn"})


@login_required
def expand_settlement(request, game_id, settlement_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    settlement = get_object_or_404(Settlement, id=settlement_id, game_id=game_id)
    if settlement.nation.player != request.user:
        return HttpResponseForbidden("You do not own this settlement")

    if settlement.nation.has_ended_turn:
        return JsonResponse({"error": "You have already ended your turn"}, status=400)

    if settlement.queued_action:
        return JsonResponse({"error": "This settlement has already acted this turn"}, status=400)

    try:
        q = int(request.POST.get("q"))
        r = int(request.POST.get("r"))
    except (TypeError, ValueError):
        return JsonResponse({"error": "Invalid coordinates"}, status=400)

    # Check if tile is adjacent to any tile belonging to the settlement
    from project.hexgrid import hex_distance
    is_adjacent = False
    owned_tiles = HexTile.objects.filter(game_id=game_id, settlement=settlement)
    for tile in owned_tiles:
        if hex_distance(tile.q, tile.r, q, r) == 1:
            is_adjacent = True
            break
            
    if not is_adjacent:
        return JsonResponse({"error": "Tile must be adjacent to the settlement territory"}, status=400)

    # Check if tile is valid and unowned
    target_tile = HexTile.objects.filter(game_id=game_id, q=q, r=r).first()
    if not target_tile or target_tile.terrain == "water":
        return JsonResponse({"error": "Invalid tile"}, status=400)
    if target_tile.owner:
        return JsonResponse({"error": "Tile already owned"}, status=400)

    # Calculate cost: base cost + 10 * number of tiles already owned
    owned_tiles_count = HexTile.objects.filter(game_id=game_id, owner=settlement.nation).count()
    cost = 10 + (owned_tiles_count * 5)

    if settlement.nation.gold < cost:
        return JsonResponse({"error": f"Not enough gold. Need {cost}"}, status=400)

    settlement.queued_action = {"type": "expand", "q": q, "r": r}
    settlement.save()
    return JsonResponse({"status": "queued", "message": "Action queued for next turn"})


@login_required
def cancel_action(request, game_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body)
        object_id = data.get("id")
        object_type = data.get("type")
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({"error": "Invalid data"}, status=400)

    if object_type == "unit":
        obj = get_object_or_404(Unit, id=object_id, game_id=game_id)
    elif object_type == "settlement":
        obj = get_object_or_404(Settlement, id=object_id, game_id=game_id)
    else:
        return JsonResponse({"error": "Invalid object type"}, status=400)

    if obj.nation.player != request.user:
        return HttpResponseForbidden("You do not own this")

    if obj.nation.has_ended_turn:
        return JsonResponse({"error": "You have already ended your turn"}, status=400)

    obj.queued_action = None
    obj.save()

    return JsonResponse({"status": "ok"})


@login_required
def friends_list(request):
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "add_friend":
            username = request.POST.get("username")
            try:
                friend_user = User.objects.get(username=username)
                if friend_user == request.user:
                    messages.error(request, "You cannot add yourself as a friend.")
                elif Friendship.objects.filter(user=request.user, friend=friend_user).exists():
                    messages.warning(request, f"You are already friends with {username}.")
                else:
                    Friendship.objects.create(user=request.user, friend=friend_user)
                    messages.success(request, f"Added {username} as a friend.")
            except User.DoesNotExist:
                messages.error(request, f"User {username} not found.")
        elif action == "remove_friend":
            friendship_id = request.POST.get("friendship_id")
            friendship = get_object_or_404(Friendship, id=friendship_id, user=request.user)
            friend_username = friendship.friend.username
            friendship.delete()
            messages.success(request, f"Removed {friend_username} from friends.")
        return redirect("hexquest:friends_list")

    friends = Friendship.objects.filter(user=request.user).select_related("friend")
    
    # Simple search: all users except self and current friends
    friend_ids = friends.values_list("friend_id", flat=True)
    search_query = request.GET.get("q", "")
    available_users = []
    if search_query:
        available_users = User.objects.filter(username__icontains=search_query).exclude(id=request.user.id).exclude(id__in=friend_ids)[:10]

    return render(request, "hexquest/friends.html", {
        "friends": friends,
        "available_users": available_users,
        "search_query": search_query,
    })
