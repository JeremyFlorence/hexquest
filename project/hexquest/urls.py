from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "hexquest"

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", auth_views.LoginView.as_view(template_name="hexquest/login_page.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("register/", views.register, name="register"),
    path("games/new/", views.create_game, name="create_game"),
    path("games/history/", views.game_history, name="game_history"),
    path("games/<int:game_id>/setup/", views.game_setup, name="game_setup"),
    path("games/<int:game_id>/map/", views.game_map, name="game_map"),
    path("games/<int:game_id>/unit/<int:unit_id>/move/", views.unit_move, name="unit_move"),
    path("games/<int:game_id>/unit/<int:unit_id>/settle/", views.unit_settle, name="unit_settle"),
    path("games/<int:game_id>/unit/<int:unit_id>/build/", views.builder_build, name="builder_build"),
    path("games/<int:game_id>/unit/<int:unit_id>/attack/", views.unit_attack, name="unit_attack"),
    path("games/<int:game_id>/building/<int:building_id>/recruit/", views.barracks_recruit, name="barracks_recruit"),
    path("games/<int:game_id>/settlement/<int:settlement_id>/upgrade/", views.upgrade_settlement, name="upgrade_settlement"),
    path("games/<int:game_id>/settlement/<int:settlement_id>/rename/", views.rename_settlement, name="rename_settlement"),
    path("games/<int:game_id>/settlement/<int:settlement_id>/expand/", views.expand_settlement, name="expand_settlement"),
    path("games/<int:game_id>/cancel-action/", views.cancel_action, name="cancel_action"),
    path("games/<int:game_id>/updates/", views.game_updates, name="game_updates"),
    path("notifications/<int:notification_id>/accept/", views.accept_invite, name="accept_invite"),
    path("notifications/<int:notification_id>/cancel/", views.cancel_invite, name="cancel_invite"),
    path("games/<int:game_id>/kick/<int:player_id>/", views.kick_player, name="kick_player"),
    path("notifications/<int:notification_id>/ignore/", views.ignore_invite, name="ignore_invite"),
    path("friends/", views.friends_list, name="friends_list"),
]