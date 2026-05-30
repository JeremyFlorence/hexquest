from django.contrib import admin
from .models import Game, Nation, HexTile, Unit, Settlement, ChatMessage, Notification

# Register your models here.
admin.site.register(Game)
admin.site.register(Nation)
admin.site.register(HexTile)
admin.site.register(Unit)
admin.site.register(Settlement)
admin.site.register(ChatMessage)
admin.site.register(Notification)
