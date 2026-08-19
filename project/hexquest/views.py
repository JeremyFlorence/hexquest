import json
from collections import Counter
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

from .models import Game, HexTile, Nation, Unit, ChatMessage, Notification, Settlement, Friendship, Building
from .consumers import broadcast_setup_update, broadcast_setup_abandoned, broadcast_game_update, broadcast_player_kicked
from .worldgen import generate_world
from project.hexgrid import hex_distance


def home(request):
    if request.GET.get("abandoned"):
        messages.warning(request, "The game creator has abandoned the game.")
    
    if request.GET.get("kicked"):
        messages.warning(request, "You have been kicked from the game lobby.")

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
            broadcast_setup_update(game)
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
                        # Check if already invited (only block if there is an UNREAD invite)
                        if not Notification.objects.filter(user=user_to_invite, game=game, notification_type="game_invite", is_read=False).exists():
                            Notification.objects.create(
                                user=user_to_invite,
                                game=game,
                                notification_type="game_invite",
                                message=f"{request.user.username} invited you to join the game '{game.name}'"
                            )
                            broadcast_setup_update(game)
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
            game.active_nation = game.nations.order_by("id").first()
            game.save()
            generate_world(game, game.width, game.height, game.seed)
            broadcast_setup_update(game)
            return redirect("hexquest:game_map", game_id=game.id)

        elif action == "abandon_game":
            if not is_creator:
                return redirect("hexquest:game_setup", game_id=game.id)
            game.is_abandoned = True
            game.save()
            abandoned_id = game.id
            game.delete()
            broadcast_setup_abandoned(abandoned_id)
            messages.success(request, "Game abandoned and deleted.")
            return redirect("hexquest:home")

        elif action == "update_nation":
            nation = get_object_or_404(Nation, game=game, player=request.user)
            nation.name = request.POST.get("nation_name", nation.name)
            nation.color = request.POST.get("color", nation.color)
            nation.save()
            broadcast_setup_update(game)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({"status": "ok"})
            return redirect("hexquest:game_setup", game_id=game.id)


    # Identify already invited or joined players to disable them in the invite dropdown
    joined_player_ids = game.nations.values_list("player_id", flat=True)
    invited_player_ids = Notification.objects.filter(
        game=game, notification_type="game_invite", is_read=False
    ).values_list("user_id", flat=True)
    unavailable_user_ids = set(joined_player_ids) | set(invited_player_ids)

    friend_ids = Friendship.objects.filter(user=request.user).values_list("friend_id", flat=True)
    users = User.objects.filter(id__in=friend_ids)
    
    for user in users:
        user.is_unavailable = user.id in unavailable_user_ids

    invitations = Notification.objects.filter(game=game, notification_type="game_invite", is_read=False)
    chat_messages = game.chat_messages.all().select_related("user")
    
    return render(
        request,
        "hexquest/game_setup.html",
        {
            "game": game,
            "nations": game.nations.all(),
            "invitations": invitations,
            "available_users": users,
            "chat_messages": chat_messages,
        },
    )


def _get_active_nation(game):
    """The nation whose turn it currently is. Falls back to the first nation
    (by join order) for games where a turn rotation hasn't started yet."""
    if game.active_nation_id:
        return game.active_nation
    return game.nations.order_by("id").first()


def _get_queued_actions(nation):
    """Helper to get all queued actions for a nation."""
    return [
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
    ] + [
        {
            "id": b.id,
            "type": "building",
            "building_type": b.building_type,
            "action": b.queued_action,
            "q": b.hex_tile.q,
            "r": b.hex_tile.r,
        } for b in Building.objects.filter(hex_tile__owner=nation).exclude(queued_action__isnull=True).select_related("hex_tile")
    ]


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
            if _get_active_nation(game) == nation:
                nation.has_ended_turn = True
                nation.save()
                process_turn_end(game)

            if request.headers.get('hx-request'):
                game.refresh_from_db()
                nation.refresh_from_db()
                remaining_time = max(0, int((game.turn_end_time - timezone.now()).total_seconds())) if game.turn_end_time else 0
                active_nation = _get_active_nation(game)
                return render(request, "hexquest/partials/game_updates_all.html", {
                    "game": game,
                    "nation": nation,
                    "active_nation": active_nation,
                    "is_my_turn": active_nation == nation,
                    "remaining_time": remaining_time,
                    "queued_actions": _get_queued_actions(nation),
                })

            return redirect("hexquest:game_map", game_id=game.id)

    # Check if timer has expired
    if game.turn_end_time and timezone.now() >= game.turn_end_time:
        process_turn_end(game)
        # Reload game after turn processing
        game.refresh_from_db()

    active_nation = _get_active_nation(game)

    hexes = (
        HexTile.objects
        .filter(game=game)
        .select_related("owner__player", "building")
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

    chat_messages = game.chat_messages.all().select_related("user")

    return render(
        request,
        "hexquest/game_map.html",
        {
            "game": game,
            "hexes": hexes,
            "units_by_position": units_by_position,
            "nation": nation,
            "active_nation": active_nation,
            "is_my_turn": active_nation == nation,
            "remaining_time": int((game.turn_end_time - timezone.now()).total_seconds()) if game.turn_end_time else 0,
            "queued_actions": _get_queued_actions(nation),
            "chat_messages": chat_messages,
            "building_costs_json": json.dumps(Building.BUILDING_COSTS),
            "unit_recruit_costs_json": json.dumps(Unit.RECRUIT_COSTS),
        },
    )


def process_turn_end(game):
    with transaction.atomic():
        # Lock the game record to prevent concurrent turn processing
        game = Game.objects.select_for_update().get(id=game.id)

        if game.is_finished:
            return

        active_nation = _get_active_nation(game)
        if active_nation is None:
            return

        # Double-check if turn should really end (either the active player
        # ended it or their timer expired)
        timer_expired = game.turn_end_time and timezone.now() >= game.turn_end_time

        if not active_nation.has_ended_turn and not timer_expired:
            return

        # Check for activity on the active player's turn
        activity_occurred = False

        # Tracks how many units currently sit on each hex, so moves processed
        # below can't push a hex over its capacity (2 units, or 1 if it has a
        # building/settlement) even when several units queue a move onto the
        # same destination in the same turn.
        occupancy = Counter(game.units.values_list("q", "r"))

        # Damage dealt this turn, so the frontend can render floating combat
        # text above the affected units.
        combat_events = []

        # Process queued actions for the active nation's units only - other
        # nations can't have queued actions since only the active nation may
        # act during its turn.
        units_with_queued = list(active_nation.units.exclude(queued_action__isnull=True))
        for unit in units_with_queued:
            activity_occurred = True
            action = unit.queued_action
            unit.queued_action = None

            if action['type'] == 'move':
                q, r = action['q'], action['r']
                if hex_distance(unit.q, unit.r, q, r) <= unit.movement:
                    target_tile = HexTile.objects.filter(game=game, q=q, r=r).select_related("settlement", "building").first()
                    if target_tile and target_tile.terrain != "water":
                        old_pos = (unit.q, unit.r)
                        new_pos = (q, r)
                        enemy_present = Unit.objects.filter(game=game, q=q, r=r).exclude(nation=unit.nation).exists()
                        if not enemy_present and (new_pos == old_pos or occupancy[new_pos] < _hex_unit_capacity(target_tile)):
                            occupancy[old_pos] -= 1
                            occupancy[new_pos] += 1
                            unit.q = q
                            unit.r = r
                            unit.last_action_turn = game.current_turn

            elif action['type'] == 'settle':
                name = action['name']
                tile = HexTile.objects.filter(game=game, q=unit.q, r=unit.r).first()
                # A settled tile can only hold 1 unit, so bail out if another
                # unit is also standing here (occupancy still counts the
                # settler itself, hence the <= 1).
                if tile and not tile.owner and unit.unit_type == 'settler' and occupancy[(unit.q, unit.r)] <= 1:
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
                        builder_placed = False
                        for n_q, n_r in hex_neighbors(tile.q, tile.r):
                            adj_tile = HexTile.objects.filter(game=game, q=n_q, r=n_r).first()
                            if adj_tile and not adj_tile.owner and adj_tile.terrain != "water":
                                adj_tile.owner = unit.nation
                                adj_tile.settlement = settlement
                                adj_tile.save()
                                # Place builder on the first available adjacent
                                # tile that isn't already occupied (it becomes
                                # settlement territory, capping it at 1 unit).
                                if not builder_placed and occupancy[(n_q, n_r)] == 0:
                                    occupancy[(unit.q, unit.r)] -= 1
                                    occupancy[(n_q, n_r)] += 1
                                    unit.q = n_q
                                    unit.r = n_r
                                    builder_placed = True
                        unit.unit_type = 'builder'
                        unit.queued_action = None
                        unit.save()
                        continue # Unit converted to builder, don't save again

            elif action['type'] == 'build':
                building_type = action['building_type']
                tile = HexTile.objects.filter(game=game, q=unit.q, r=unit.r).first()
                allowed_terrain = Building.BUILDING_TERRAIN.get(building_type)
                terrain_ok = tile and tile.terrain != "water" and (not allowed_terrain or tile.terrain in allowed_terrain)
                if tile and unit.unit_type == 'builder' and tile.owner == unit.nation and terrain_ok:
                    if not hasattr(tile, 'building') or not tile.building:
                        cost = Building.BUILDING_COSTS.get(building_type, 0)
                        if unit.nation.gold >= cost:
                            unit.nation.gold -= cost
                            unit.nation.save()
                            Building.objects.create(
                                game=game,
                                hex_tile=tile,
                                building_type=building_type
                            )
                            unit.last_action_turn = game.current_turn

            elif action['type'] == 'attack':
                target = Unit.objects.filter(game=game, id=action['target_id']).first()
                if target and target.nation_id != unit.nation_id and hex_distance(unit.q, unit.r, target.q, target.r) == 1:
                    unit.last_action_turn = game.current_turn
                    damage = Unit.roll_damage(unit.attack)
                    target.hitpoints -= damage
                    combat_events.append({"q": target.q, "r": target.r, "damage": damage})
                    if target.hitpoints <= 0:
                        occupancy[(target.q, target.r)] -= 1
                        target.delete()
                    else:
                        counter_damage = Unit.roll_damage(target.defense)
                        unit.hitpoints -= counter_damage
                        combat_events.append({"q": unit.q, "r": unit.r, "damage": counter_damage})
                        target.save()
                    if unit.hitpoints <= 0:
                        occupancy[(unit.q, unit.r)] -= 1
                        unit.delete()
                        continue  # Attacker died, don't save it below

            unit.save()

        # Process queued actions for the active nation's buildings (e.g.
        # barracks recruiting a new unit) only
        buildings_with_queued = list(
            Building.objects.filter(game=game, hex_tile__owner=active_nation)
            .exclude(queued_action__isnull=True)
            .select_related("hex_tile")
        )
        for building in buildings_with_queued:
            activity_occurred = True
            action = building.queued_action
            building.queued_action = None

            if action['type'] == 'recruit':
                unit_type = action['unit_type']
                cost = Unit.RECRUIT_COSTS.get(unit_type, 0)
                nation = active_nation
                if nation.gold >= cost:
                    spawn_tile = building.hex_tile
                    target_tile = None
                    if occupancy[(spawn_tile.q, spawn_tile.r)] < _hex_unit_capacity(spawn_tile):
                        target_tile = spawn_tile
                    else:
                        from project.hexgrid import hex_neighbors
                        for n_q, n_r in hex_neighbors(spawn_tile.q, spawn_tile.r):
                            adj_tile = HexTile.objects.filter(game=game, q=n_q, r=n_r).select_related("settlement", "building").first()
                            if (adj_tile and adj_tile.owner_id == nation.id and adj_tile.terrain != "water"
                                    and occupancy[(n_q, n_r)] < _hex_unit_capacity(adj_tile)):
                                target_tile = adj_tile
                                break

                    if target_tile:
                        nation.gold -= cost
                        nation.save()
                        stats = Unit.stats_for(unit_type)
                        Unit.objects.create(
                            game=game,
                            nation=nation,
                            q=target_tile.q,
                            r=target_tile.r,
                            unit_type=unit_type,
                            hitpoints=stats["hitpoints"],
                            attack=stats["attack"],
                            defense=stats["defense"],
                            last_action_turn=game.current_turn,
                        )
                        occupancy[(target_tile.q, target_tile.r)] += 1

            building.save()

        # Process queued actions for the active nation's settlements only
        settlements_with_queued = list(active_nation.settlements.exclude(queued_action__isnull=True))
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
            game.round_activity_occurred = True

        # Update only this field (rather than active_nation.save()) so we
        # don't clobber gold/food changes made above via separately-fetched
        # instances of the same nation row (e.g. unit.nation, settlement.nation).
        Nation.objects.filter(id=active_nation.id).update(has_ended_turn=False)

        # Determine who goes next, rotating through nations in join order.
        # Wrapping back around to the first nation means a full round (every
        # player has had one turn) has completed.
        nations_ordered = list(game.nations.order_by("id"))
        try:
            current_index = nations_ordered.index(active_nation)
        except ValueError:
            current_index = -1
        next_index = (current_index + 1) % len(nations_ordered)
        round_complete = next_index == 0
        next_nation = nations_ordered[next_index]

        if round_complete:
            # Process resource generation from buildings once per round
            for building in game.buildings.all():
                if building.building_type == "wheat_farm":
                    building.hex_tile.owner.food += 2
                    building.hex_tile.owner.save()

            if game.round_activity_occurred:
                game.last_activity_turn = game.current_turn

            # Check for game end condition (3 rounds without activity)
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
            game.round_activity_occurred = False

        game.turn_end_time = timezone.now() + datetime.timedelta(seconds=game.turn_timer)
        if not game.is_finished:
            game.active_nation = next_nation
        game.save()

        broadcast_game_update(game, combat_events=combat_events)


@login_required
def game_updates(request, game_id):
    game = get_object_or_404(Game, id=game_id)
    nation = get_object_or_404(Nation, game=game, player=request.user)
    
    # Check if timer has expired
    if game.turn_end_time and timezone.now() >= game.turn_end_time:
        process_turn_end(game)
        game.refresh_from_db()

    remaining_time = int((game.turn_end_time - timezone.now()).total_seconds()) if game.turn_end_time else 0
    active_nation = _get_active_nation(game)

    if request.headers.get('hx-request'):
        return render(request, "hexquest/partials/game_updates_all.html", {
            "game": game,
            "nation": nation,
            "active_nation": active_nation,
            "is_my_turn": active_nation == nation,
            "remaining_time": max(0, remaining_time),
            "queued_actions": _get_queued_actions(nation),
        })

    return JsonResponse({
        "current_turn": game.current_turn,
        "remaining_time": max(0, remaining_time),
        "has_ended_turn": nation.has_ended_turn,
        "is_my_turn": active_nation == nation,
        "active_player_id": active_nation.player_id if active_nation else None,
        "active_nation_name": active_nation.name if active_nation else None,
        "gold": nation.gold,
        "food": nation.food,
        "unit_count": nation.units.count(),
        "queued_actions": _get_queued_actions(nation),
    })




@login_required
def cancel_invite(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, notification_type="game_invite")
    game = notification.game
    if game.creator != request.user:
        return HttpResponseForbidden("Only the game creator can cancel invitations.")
    
    notification.delete()
    broadcast_setup_update(game)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({"status": "ok"})
    return redirect("hexquest:game_setup", game_id=game.id)


@login_required
def kick_player(request, game_id, player_id):
    game = get_object_or_404(Game, id=game_id)
    if game.creator != request.user:
        return HttpResponseForbidden("Only the game creator can kick players.")
    
    if int(player_id) == game.creator.id:
        return HttpResponseForbidden("You cannot kick yourself.")
    
    player_to_kick = get_object_or_404(User, id=player_id)
    nation = get_object_or_404(Nation, game=game, player=player_to_kick)
    nation.delete()

    # Also delete any existing invitations for this player in this game so they can be re-invited
    Notification.objects.filter(user=player_to_kick, game=game, notification_type="game_invite").delete()

    broadcast_player_kicked(game.id, int(player_id))
    broadcast_setup_update(game)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({"status": "ok"})
    return redirect("hexquest:game_setup", game_id=game.id)


@login_required
def accept_invite(request, notification_id):
    try:
        notification = Notification.objects.get(id=notification_id, user=request.user)
    except Notification.DoesNotExist:
        messages.error(request, "This invitation has been cancelled or no longer exists.")
        return redirect("hexquest:home")
    
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
    broadcast_setup_update(game)
    return redirect("hexquest:game_setup", game_id=game.id)


def _hex_unit_capacity(tile):
    """A hex holds at most 2 units, or 1 if it has a building or settlement."""
    has_structure = bool(tile.settlement_id) or (hasattr(tile, "building") and tile.building is not None)
    return 1 if has_structure else 2


@login_required
def unit_move(request, game_id, unit_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    unit = get_object_or_404(Unit, id=unit_id, game_id=game_id)
    if unit.nation.player != request.user:
        return HttpResponseForbidden("You do not own this unit")

    if _get_active_nation(unit.game) != unit.nation:
        return JsonResponse({"error": "It is not your turn"}, status=400)

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
    target_tile = HexTile.objects.filter(game_id=game_id, q=q, r=r).select_related("settlement", "building").first()
    if not target_tile or target_tile.terrain == "water":
        return JsonResponse({"error": "Cannot move there"}, status=400)

    # Check hex capacity (this is an early check for immediate feedback;
    # process_turn_end re-validates authoritatively since other units may
    # also queue a move onto the same hex this turn).
    occupants = Unit.objects.filter(game_id=game_id, q=q, r=r).exclude(id=unit.id)
    if occupants.exclude(nation=unit.nation).exists():
        return JsonResponse({"error": "Destination hex is occupied by an enemy unit. Attack it instead."}, status=400)
    if occupants.count() >= _hex_unit_capacity(target_tile):
        return JsonResponse({"error": "Destination hex is full"}, status=400)

    unit.queued_action = {"type": "move", "q": q, "r": r}
    unit.save()
    broadcast_game_update(unit.game, user=request.user)
    return JsonResponse({"status": "queued", "message": "Action queued for next turn"})


@login_required
def unit_attack(request, game_id, unit_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    unit = get_object_or_404(Unit, id=unit_id, game_id=game_id)
    if unit.nation.player != request.user:
        return HttpResponseForbidden("You do not own this unit")

    if _get_active_nation(unit.game) != unit.nation:
        return JsonResponse({"error": "It is not your turn"}, status=400)

    if unit.queued_action:
        return JsonResponse({"error": "This unit has already acted this turn"}, status=400)

    if unit.unit_type not in Unit.COMBAT_UNIT_TYPES:
        return JsonResponse({"error": "Only combat units can attack"}, status=400)

    try:
        target_id = int(request.POST.get("target_id"))
    except (TypeError, ValueError):
        return JsonResponse({"error": "Invalid target"}, status=400)

    target = get_object_or_404(Unit, id=target_id, game_id=game_id)
    if target.nation_id == unit.nation_id:
        return JsonResponse({"error": "Cannot attack your own unit"}, status=400)

    if hex_distance(unit.q, unit.r, target.q, target.r) != 1:
        return JsonResponse({"error": "Target is not adjacent"}, status=400)

    unit.queued_action = {"type": "attack", "target_id": target.id}
    unit.save()
    broadcast_game_update(unit.game, user=request.user)
    return JsonResponse({"status": "queued", "message": "Action queued for next turn"})


@login_required
def unit_settle(request, game_id, unit_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    unit = get_object_or_404(Unit, id=unit_id, game_id=game_id)
    if unit.nation.player != request.user:
        return HttpResponseForbidden("You do not own this unit")

    if _get_active_nation(unit.game) != unit.nation:
        return JsonResponse({"error": "It is not your turn"}, status=400)

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
    broadcast_game_update(unit.game, user=request.user)
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


@login_required
def ignore_invite(request, notification_id):
    try:
        notification = Notification.objects.get(id=notification_id, user=request.user)
    except Notification.DoesNotExist:
        messages.error(request, "This invitation has been cancelled or no longer exists.")
        return redirect("hexquest:home")
    
    game = notification.game
    notification.is_read = True
    notification.save()
    if game:
        broadcast_setup_update(game)
    return redirect("hexquest:home")


@login_required
def upgrade_settlement(request, game_id, settlement_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    settlement = get_object_or_404(Settlement, id=settlement_id, game_id=game_id)
    if settlement.nation.player != request.user:
        return HttpResponseForbidden("You do not own this settlement")

    if _get_active_nation(settlement.game) != settlement.nation:
        return JsonResponse({"error": "It is not your turn"}, status=400)

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
    broadcast_game_update(settlement.game, user=request.user)
    return JsonResponse({"status": "queued", "message": "Action queued for next turn"})


@login_required
def expand_settlement(request, game_id, settlement_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    settlement = get_object_or_404(Settlement, id=settlement_id, game_id=game_id)
    if settlement.nation.player != request.user:
        return HttpResponseForbidden("You do not own this settlement")

    if _get_active_nation(settlement.game) != settlement.nation:
        return JsonResponse({"error": "It is not your turn"}, status=400)

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
    broadcast_game_update(settlement.game, user=request.user)
    return JsonResponse({"status": "queued", "message": "Action queued for next turn"})


@login_required
def builder_build(request, game_id, unit_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    unit = get_object_or_404(Unit, id=unit_id, game_id=game_id)
    if unit.nation.player != request.user:
        return HttpResponseForbidden("You do not own this unit")

    if _get_active_nation(unit.game) != unit.nation:
        return JsonResponse({"error": "It is not your turn"}, status=400)

    if unit.queued_action:
        return JsonResponse({"error": "This unit has already acted this turn"}, status=400)

    if unit.unit_type != "builder":
        return JsonResponse({"error": "Only builders can build structures"}, status=400)

    building_type = request.POST.get("type")
    if building_type not in Building.BUILDING_COSTS:
        return JsonResponse({"error": "Unknown building type"}, status=400)

    tile = HexTile.objects.filter(game_id=game_id, q=unit.q, r=unit.r).first()
    if not tile:
        return JsonResponse({"error": "Tile not found"}, status=404)

    if tile.owner != unit.nation:
        return JsonResponse({"error": "You do not own this tile"}, status=400)

    allowed_terrain = Building.BUILDING_TERRAIN.get(building_type)
    if tile.terrain == "water" or (allowed_terrain and tile.terrain not in allowed_terrain):
        return JsonResponse({"error": f"{building_type.replace('_', ' ').title()} cannot be built here"}, status=400)

    if hasattr(tile, 'building') and tile.building:
        return JsonResponse({"error": "A building already exists on this tile"}, status=400)

    cost = Building.BUILDING_COSTS.get(building_type, 0)
    if unit.nation.gold < cost:
        return JsonResponse({"error": f"Not enough gold. Need {cost}"}, status=400)

    unit.queued_action = {"type": "build", "building_type": building_type}
    unit.save()
    broadcast_game_update(unit.game, user=request.user)
    return JsonResponse({"status": "queued", "message": "Action queued for next turn"})


@login_required
def barracks_recruit(request, game_id, building_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    building = get_object_or_404(Building, id=building_id, game_id=game_id)
    nation = building.hex_tile.owner
    if not nation or nation.player != request.user:
        return HttpResponseForbidden("You do not own this building")

    if _get_active_nation(building.game) != nation:
        return JsonResponse({"error": "It is not your turn"}, status=400)

    if building.building_type != "barracks":
        return JsonResponse({"error": "Only barracks can recruit units"}, status=400)

    if building.queued_action:
        return JsonResponse({"error": "This building has already acted this turn"}, status=400)

    unit_type = request.POST.get("unit_type")
    if unit_type not in Unit.RECRUIT_COSTS:
        return JsonResponse({"error": "Unknown unit type"}, status=400)

    cost = Unit.RECRUIT_COSTS[unit_type]
    if nation.gold < cost:
        return JsonResponse({"error": f"Not enough gold. Need {cost}"}, status=400)

    building.queued_action = {"type": "recruit", "unit_type": unit_type}
    building.save()
    broadcast_game_update(building.game, user=request.user)
    return JsonResponse({"status": "queued", "message": "Action queued for next turn"})


@login_required
def cancel_action(request, game_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    if request.content_type == "application/json":
        try:
            data = json.loads(request.body)
            object_id = data.get("id")
            object_type = data.get("type")
        except (json.JSONDecodeError, AttributeError):
            return JsonResponse({"error": "Invalid data"}, status=400)
    else:
        object_id = request.POST.get("id")
        object_type = request.POST.get("type")

    if object_type == "unit":
        obj = get_object_or_404(Unit, id=object_id, game_id=game_id)
        nation = obj.nation
    elif object_type == "settlement":
        obj = get_object_or_404(Settlement, id=object_id, game_id=game_id)
        nation = obj.nation
    elif object_type == "building":
        obj = get_object_or_404(Building, id=object_id, game_id=game_id)
        nation = obj.hex_tile.owner
    else:
        return JsonResponse({"error": "Invalid object type"}, status=400)

    if not nation or nation.player != request.user:
        return HttpResponseForbidden("You do not own this")

    if _get_active_nation(obj.game) != nation:
        return JsonResponse({"error": "It is not your turn"}, status=400)

    obj.queued_action = None
    obj.save()
    broadcast_game_update(obj.game, user=request.user)

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
