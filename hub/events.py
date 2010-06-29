# |ALPHA| Hub - an authorization server for alpha-ioq3
# See files README and COPYING for copyright and licensing details.

"""
events.py - events broadcast through circuits

TODO: web site events?
"""

from circuits import Event


class GameServerEvent(Event):
    """Event directly from game server (trusted implicitly)."""

class ServerUserinfoChanged(GameServerEvent):
    """Userinfo changed."""

class PlayerAdminRequest(GameServerEvent):
    """Player needs administrator. TODO: really? how? voting?"""

class AdminLogin(GameServerEvent):
    """Administrator wants authorization."""

class AdminBanRequest(GameServerEvent):
    """Administrator bans player."""

class AdminCheckPlayer(GameServerEvent):
    """Administrator checks player."""


class HubServerEvent(Event):
    """Event from another hub (not necessarily trusted)."""

class HubUserinfoChanged(HubServerEvent):
    """Userinfo changed on someone else's game server."""

class HubBanNotification(HubServerEvent):
    """Ban established on someone else's hub."""


class GameServerReply(Event):
    """Event directly to game server."""

class BanNotification(GameServerReply):
    """Notification of existing ban."""

class AdminAuthorized(Event):
    """Notification of administrator credentials."""


class WebRequest(Event):
    """Event from the website."""

class WebLogin(Event):
    """User wants authorization."""

class WebLogout(Event):
    """User leaves."""

class WebDashboard(Event):
    """User wants dashboard."""

class WebPlayerList(Event):
    """User wants player list."""

class WebPlayerDetail(Event):
    """User wants player details."""

class WebBanList(Event):
    """User wants ban list."""

class WebBanDetail(Event):
    """User wants ban details."""

class WebBanEdit(Event):
    """User edits ban."""

class WebBanCreate(Event):
    """User creates ban."""


class WebResponse(Event):
    """Event to the website."""
