import threading
import time
import logging
from django.db import close_old_connections
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)

def start_timer_thread():
    """Starts a background thread that handles game timer ticks and turn expiration."""
    thread = threading.Thread(target=_timer_worker, daemon=True)
    thread.start()
    logger.info("Game timer heartbeat thread started.")

def _timer_worker():
    # Delay import to avoid circular dependency or apps not being ready
    from .models import Game
    from .views import process_turn_end
    
    channel_layer = get_channel_layer()
    if not channel_layer:
        logger.error("Channel layer not available for timer heartbeat.")
        return

    while True:
        try:
            # This loop runs on a plain background thread, outside Django's
            # request/response cycle and outside Channels' database_sync_to_async
            # wrapper — neither of which is here to recycle a stale or broken
            # connection for us. Do it explicitly so a dropped connection
            # (e.g. a pooler hiccup) doesn't permanently wedge the heartbeat.
            close_old_connections()

            # Only process active, non-finished games
            active_games = Game.objects.filter(is_active=True, is_finished=False)
            
            for game in active_games:
                if not game.turn_end_time:
                    continue
                
                now = timezone.now()
                remaining = int((game.turn_end_time - now).total_seconds())
                
                if remaining <= 0:
                    # Time is up! Advancing turn proactively.
                    try:
                        process_turn_end(game)
                    except Exception as e:
                        logger.error(f"Error processing turn end for game {game.id}: {e}")
                else:
                    # Broadcast tick to the game group
                    # We send this to all connected clients so they can sync their timers
                    async_to_sync(channel_layer.group_send)(
                        f"game_{game.id}",
                        {
                            "type": "game.timer_tick",
                            "remaining_time": remaining
                        }
                    )
            
            # Tick every second
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"Timer heartbeat worker error: {e}")
            time.sleep(5)
