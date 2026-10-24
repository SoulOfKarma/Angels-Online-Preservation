"""Single account owner across login -> world; synchronous event-loop operations."""
import time


class Accesos:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.owners = {}
        self.tickets = {}

    def limpiar(self):
        now = self.clock()
        for ip, (_, _, _, fin) in list(self.tickets.items()):
            if fin <= now:
                del self.tickets[ip]
        for key, ses in list(self.owners.items()):
            if getattr(ses, 'desconectado', False) and not any(t[0] is ses for t in self.tickets.values()):
                del self.owners[key]

    def login(self, ses, user):
        self.limpiar()
        key = user.casefold()
        if getattr(ses, '_cuenta_autenticada', key) != key:
            return False
        if key in self.owners and self.owners[key] is not ses:
            return False
        self.owners[key] = ses
        ses._cuenta_autenticada = key
        return True

    def reservar(self, ses, ip, slot):
        self.limpiar()
        key = getattr(ses, '_cuenta_autenticada', None)
        if key is None or self.owners.get(key) is not ses:
            return False
        old = self.tickets.get(ip)
        if old and old[0] is not ses:
            return False  # Never overwrite another client's pending handoff behind NAT.
        self.tickets[ip] = (ses, ses.usuario, slot, self.clock()+30)
        return True

    def mundo(self, ses, ip):
        self.limpiar()
        ticket = self.tickets.pop(ip, None)
        if ticket is None:
            return None
        login, user, slot, _ = ticket
        key = user.casefold()
        if self.owners.get(key) is not login:
            return None
        self.owners[key] = ses
        ses._cuenta_autenticada = key
        return user, slot

    def salir(self, ses):
        key = getattr(ses, '_cuenta_autenticada', None)
        if self.owners.get(key) is ses and not any(t[0] is ses for t in self.tickets.values()):
            del self.owners[key]
