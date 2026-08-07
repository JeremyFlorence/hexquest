from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"^ws/chat/(?P<game_id>\d+)/$", consumers.ChatConsumer.as_asgi()),
    re_path(r"^ws/setup/(?P<game_id>\d+)/$", consumers.SetupConsumer.as_asgi()),
    re_path(r"^ws/game/(?P<game_id>\d+)/$", consumers.GameConsumer.as_asgi()),
]
