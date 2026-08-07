from django.apps import AppConfig


class HexquestConfig(AppConfig):
    name = 'hexquest'

    def ready(self):
        # Start the background timer heartbeat thread
        import os
        # Only start the thread in the main process, not in auto-reloaders or other child processes
        if os.environ.get('RUN_MAIN') == 'true' or not os.environ.get('DEBUG') == 'True':
            from .timer import start_timer_thread
            start_timer_thread()
