import threading
import time


class Unbanner:
    def __init__(self, blocker):
        self.blocker = blocker

    def schedule_unban(self, ip, duration):
        if duration < 0:
            return
        t = threading.Timer(duration, self.blocker._unban, args=[ip])
        t.daemon = True
        t.start()
