from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.layers import get_channel_layer

from .models import ChatMessage, Game


def _chat_group(game_id):
    return f"chat_game_{game_id}"


def _setup_group(game_id):
    return f"setup_game_{game_id}"


def _game_group(game_id):
    return f"game_{game_id}"


def _user_game_group(game_id, user_id):
    return f"game_{game_id}_user_{user_id}"


def _serialize_setup(game):
    return {
        "nations": [
            {
                "player": n.player.username,
                "name": n.name,
                "color": n.color,
            }
            for n in game.nations.select_related("player").all()
        ],
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
    }


def broadcast_setup_update(game):
    """Broadcast the current lobby setup state to all connected clients."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    payload = _serialize_setup(game)
    async_to_sync(channel_layer.group_send)(
        _setup_group(game.id),
        {"type": "setup.update", "payload": payload},
    )


def broadcast_setup_abandoned(game_id):
    """Notify connected clients that the game has been abandoned."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        _setup_group(game_id),
        {"type": "setup.abandoned"},
    )


def _serialize_game_update(game, nation):
    from django.utils import timezone
    remaining_time = int((game.turn_end_time - timezone.now()).total_seconds()) if game.turn_end_time else 0
    return {
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
    }


def broadcast_game_update(game, user=None):
    """
    Broadcast game updates. If user is provided, only sends to that user's group.
    Otherwise, sends to all players in the game (looping through their nations).
    """
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    if user:
        try:
            nation = game.nations.get(player=user)
            payload = _serialize_game_update(game, nation)
            async_to_sync(channel_layer.group_send)(
                _user_game_group(game.id, user.id),
                {"type": "game.update", "payload": payload},
            )
        except Exception:
            pass
    else:
        # Broadcast to all players in the game
        for nation in game.nations.select_related("player").all():
            payload = _serialize_game_update(game, nation)
            async_to_sync(channel_layer.group_send)(
                _user_game_group(game.id, nation.player.id),
                {"type": "game.update", "payload": payload},
            )
        # Also notify general group (e.g. for map refresh if needed, though we try to be surgical)
        async_to_sync(channel_layer.group_send)(
            _game_group(game.id),
            {"type": "game.refresh"},
        )


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
