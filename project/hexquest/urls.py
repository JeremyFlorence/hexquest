from django.urls import path

from . import views

app_name = "hexquest"

urlpatterns = [
    path("", views.home, name="home"),
    path("register/", views.register, name="register"),
    path("games/new/", views.create_game, name="create_game"),
    path("games/<int:game_id>/map/", views.game_map, name="game_map"),
]