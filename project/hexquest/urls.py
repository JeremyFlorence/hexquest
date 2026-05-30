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
    path("games/<int:game_id>/setup/", views.game_setup, name="game_setup"),
    path("games/<int:game_id>/setup/updates/", views.game_setup_updates, name="game_setup_updates"),
    path("games/<int:game_id>/map/", views.game_map, name="game_map"),
    path("notifications/<int:notification_id>/accept/", views.accept_invite, name="accept_invite"),
    path("notifications/<int:notification_id>/ignore/", views.ignore_invite, name="ignore_invite"),
]