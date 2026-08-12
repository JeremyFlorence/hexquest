import asyncio
from concurrent.futures import ThreadPoolExecutor
from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.layers import get_channel_layer

from .models import Building, ChatMessage, Game, HexTile, Nation, Unit, Settlement


_BROADCAST_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="broadcast")


def _dispatch_async(coro_func):
    def _runner():
        try:
            async_to_sync(coro_func)()
        except BaseException:
            pass

    try:
        _BROADCAST_EXECUTOR.submit(_runner)
    except BaseException:
        pass


def _chat_group(game_id):
    return f"chat_game_{game_id}"


def _setup_group(game_id):
    return f"setup_game_{game_id}"


def _game_group(game_id):
    return f"game_{game_id}"


def _user_game_group(game_id, user_id):
    return f"game_{game_id}_user_{user_id}"


def _serialize_setup(game):
    from .models import Notification
    return {
        "nations": [
            {
                "player": n.player.username,
                "player_id": n.player.id,
                "name": n.name,
                "color": n.color,
            }
            for n in game.nations.select_related("player").all()
        ],
        "invitations": [
            {
                "id": i.id,
                "player": i.user.username,
            }
            for i in Notification.objects.filter(game=game, notification_type="game_invite", is_read=False).select_related("user")
        ],
        "unavailable_players": (
            list(game.nations.values_list("player__username", flat=True)) +
            list(Notification.objects.filter(
                game=game, notification_type="game_invite", is_read=False
            ).values_list("user__username", flat=True))
        ),
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
        },
        "creator": game.creator.username if game.creator else None,
    }


def broadcast_setup_update(game):
    """Broadcast the current lobby setup state to all connected clients."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    payload = _serialize_setup(game)

    async def _do_send():
        await channel_layer.group_send(
            _setup_group(game.id),
            {"type": "setup.update", "payload": payload},
        )

    _dispatch_async(_do_send)


def broadcast_player_kicked(game_id, player_id):
    """Notify a specific player that they have been kicked from the lobby."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    async def _do_send():
        await channel_layer.group_send(
            _setup_group(game_id),
            {"type": "setup.kicked", "player_id": player_id},
        )

    _dispatch_async(_do_send)


def broadcast_setup_abandoned(game_id):
    """Notify connected clients that the game has been abandoned."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    async def _do_send():
        await channel_layer.group_send(
            _setup_group(game_id),
            {"type": "setup.abandoned"},
        )

    _dispatch_async(_do_send)


def _building_type(hex_tile):
    try:
        return hex_tile.building.building_type
    except Building.DoesNotExist:
        return None


def _get_active_nation(game):
    """The nation whose turn it currently is. Falls back to the first nation
    (by join order) for games where a turn rotation hasn't started yet."""
    if game.active_nation_id:
        return game.active_nation
    return game.nations.order_by("id").first()


def _serialize_game_update(game, nation, all_units=None, all_settlements=None, all_hexes=None):
    from django.utils import timezone
    remaining_time = int((game.turn_end_time - timezone.now()).total_seconds()) if game.turn_end_time else 0
    active_nation = _get_active_nation(game)

    if all_units is None:
        all_units = list(Unit.objects.filter(game=game).select_related("nation__player").all())
    if all_settlements is None:
        all_settlements = list(Settlement.objects.filter(game=game).select_related("nation__player").all())
    if all_hexes is None:
        all_hexes = list(HexTile.objects.filter(game=game).select_related("owner__player", "settlement", "building").all())

    return {
        "is_finished": game.is_finished,
        "current_turn": game.current_turn,
        "remaining_time": max(0, remaining_time),
        "has_ended_turn": nation.has_ended_turn,
        "is_my_turn": active_nation.id == nation.id if active_nation else False,
        "active_player_id": active_nation.player_id if active_nation else None,
        "active_nation_name": active_nation.name if active_nation else None,
        "gold": nation.gold,
        "food": nation.food,
        "unit_count": len([u for u in all_units if u.nation_id == nation.id]),
        "units": [
            {
                "id": u.id,
                "type": u.unit_type,
                "q": u.q,
                "r": u.r,
                "color": u.nation.color,
                "label": u.unit_type[0].upper(),
                "owner_id": u.nation.player.id,
                "owner_name": u.nation.player.username,
                "owner_nation": u.nation.name,
                "last_action_turn": u.last_action_turn,
                "queued_action": bool(u.queued_action)
            } for u in all_units
        ],
        "settlements": [
            {
                "id": s.id,
                "q": s.q,
                "r": s.r,
                "name": s.name,
                "tier": s.tier,
                "color": s.nation.color,
                "population": s.population,
                "owner_id": s.nation.player.id,
                "owner_name": s.nation.player.username,
                "owner_nation": s.nation.name,
                "last_action_turn": s.last_action_turn,
                "queued_action": bool(s.queued_action)
            } for s in all_settlements
        ],
        "hexes": [
            {
                "q": h.q,
                "r": h.r,
                "owner": h.owner.name if h.owner else None,
                "owner_id": h.owner.player.id if h.owner else None,
                "owner_color": h.owner.color if h.owner else None,
                "settlement": h.settlement.name if h.settlement else None,
                "settlement_id": h.settlement.id if h.settlement else None,
                "building": _building_type(h)
            } for h in all_hexes
        ],
        "queued_actions": [
            {
                "id": u.id,
                "type": "unit",
                "unit_type": u.unit_type,
                "action": u.queued_action,
                "q": u.q,
                "r": u.r
            } for u in all_units if u.nation_id == nation.id and u.queued_action
        ] + [
            {
                "id": s.id,
                "type": "settlement",
                "name": s.name,
                "action": s.queued_action,
                "q": s.q,
                "r": s.r
            } for s in all_settlements if s.nation_id == nation.id and s.queued_action
        ]
    }


def broadcast_game_update(game, user=None):
    """
    Broadcast game updates. If user is provided, only sends to that user's group.
    Otherwise, sends to all players in the game (looping through their nations).
    """
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    # Prepare all payloads in sync context to ensure transaction visibility
    # and to avoid N+1 queries in the async loop.
    all_units = list(Unit.objects.filter(game=game).select_related("nation__player").all())
    all_settlements = list(Settlement.objects.filter(game=game).select_related("nation__player").all())
    all_hexes = list(HexTile.objects.filter(game=game).select_related("owner__player", "settlement", "building").all())

    broadcasts = []
    if user:
        try:
            nation = game.nations.get(player=user)
            payload = _serialize_game_update(game, nation, all_units, all_settlements, all_hexes)
            broadcasts.append((_user_game_group(game.id, user.id), payload))
        except Exception:
            pass
    else:
        for nation in game.nations.select_related("player").all():
            payload = _serialize_game_update(game, nation, all_units, all_settlements, all_hexes)
            broadcasts.append((_user_game_group(game.id, nation.player.id), payload))

    if not broadcasts:
        return

    async def _do_broadcast():
        tasks = []
        for group_name, payload in broadcasts:
            tasks.append(channel_layer.group_send(
                group_name,
                {"type": "game.update", "payload": payload},
            ))
        if tasks:
            await asyncio.gather(*tasks)

    _dispatch_async(_do_broadcast)


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get("user")
        if not self.user or not self.user.is_authenticated:
            await self.close()
            return

        self.game_id = self.scope["url_route"]["kwargs"]["game_id"]
        self.group_name = _chat_group(self.game_id)

        if not await self._user_in_game(self.user.id, self.game_id):
            await self.close()
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        text = (content.get("text") or "").strip()
        if not text:
            return

        msg = await self._save_message(self.game_id, self.user.id, text)
        if msg is None:
            return

        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "chat.message",
                "message": {
                    "id": msg["id"],
                    "user": msg["user"],
                    "text": msg["text"],
                    "created_at": msg["created_at"],
                },
            },
        )

    async def chat_message(self, event):
        await self.send_json({"type": "chat_message", "message": event["message"]})

    @database_sync_to_async
    def _user_in_game(self, user_id, game_id):
        return Game.objects.filter(id=game_id, nations__player_id=user_id).exists()

    @database_sync_to_async
    def _save_message(self, game_id, user_id, text):
        if not Game.objects.filter(id=game_id, nations__player_id=user_id).exists():
            return None
        msg = ChatMessage.objects.create(game_id=game_id, user_id=user_id, text=text)
        return {
            "id": msg.id,
            "user": msg.user.username,
            "text": msg.text,
            "created_at": msg.created_at.strftime("%H:%M"),
        }


class SetupConsumer(AsyncJsonWebsocketConsumer):
    """Real-time lobby updates for the game setup page (nations, settings, start)."""

    async def connect(self):
        self.user = self.scope.get("user")
        if not self.user or not self.user.is_authenticated:
            await self.close()
            return

        self.game_id = self.scope["url_route"]["kwargs"]["game_id"]
        self.group_name = _setup_group(self.game_id)

        state = await self._get_initial_state(self.user.id, self.game_id)
        if state is None:
            await self.close()
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        # Send current state on connect so no polling is needed.
        await self.send_json({"type": "setup_update", "payload": state})

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def setup_update(self, event):
        await self.send_json({"type": "setup_update", "payload": event["payload"]})

    async def setup_abandoned(self, event):
        await self.send_json({"type": "setup_abandoned"})

    async def setup_kicked(self, event):
        await self.send_json({"type": "setup_kicked", "player_id": event["player_id"]})

    @database_sync_to_async
    def _get_initial_state(self, user_id, game_id):
        game = (
            Game.objects
            .filter(id=game_id, nations__player_id=user_id)
            .first()
        )
        if game is None:
            return None
        return _serialize_setup(game)


class GameConsumer(AsyncJsonWebsocketConsumer):
    """Real-time game updates (resources, turns, map changes)."""

    async def connect(self):
        self.user = self.scope.get("user")
        if not self.user or not self.user.is_authenticated:
            await self.close()
            return

        self.game_id = self.scope["url_route"]["kwargs"]["game_id"]
        self.game_group = _game_group(self.game_id)
        self.user_group = _user_game_group(self.game_id, self.user.id)

        state = await self._get_initial_state(self.user.id, self.game_id)
        if state is None:
            await self.close()
            return

        await self.channel_layer.group_add(self.game_group, self.channel_name)
        await self.channel_layer.group_add(self.user_group, self.channel_name)
        await self.accept()
        
        # Send initial state
        await self.send_json({"type": "game_update", "payload": state})

    async def disconnect(self, code):
        if hasattr(self, "game_group"):
            await self.channel_layer.group_discard(self.game_group, self.channel_name)
        if hasattr(self, "user_group"):
            await self.channel_layer.group_discard(self.user_group, self.channel_name)

    async def game_update(self, event):
        await self.send_json({"type": "game_update", "payload": event["payload"]})

    async def game_refresh(self, event):
        """Signal to client to reload or fetch fresh map data if needed."""
        await self.send_json({"type": "game_refresh"})

    async def game_timer_tick(self, event):
        """Send a timer tick to the client."""
        await self.send_json({
            "type": "timer_tick",
            "remaining_time": event["remaining_time"]
        })

    @database_sync_to_async
    def _get_initial_state(self, user_id, game_id):
        game = Game.objects.filter(id=game_id).first()
        if not game:
            return None
        try:
            nation = game.nations.get(player_id=user_id)
            return _serialize_game_update(game, nation)
        except Exception:
            return None
