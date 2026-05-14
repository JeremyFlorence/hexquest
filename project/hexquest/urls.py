from django.urls import path

from . import views

app_name = "hexquest"

urlpatterns = [
    path("games/<int:game_id>/map/", views.game_map, name="game_map"),
]