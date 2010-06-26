# |ALPHA| Hub - an authorization server for alpha-ioq3
# See files README and COPYING for copyright and licensing details.

"""
model.py - data model

- some model classes perform important conversions on data
  handed to them; see User.password for example

- some model classes perform important sanity checks on data
  handed to them; TODO: need an example

- all times are in UTC in the model; convert in the user
  interface if necessary

- string lengths are somewhat contentious between database
  systems; for example MySQL apparently doesn't like variable
  length strings quite as much as SQLite; so we use fixed
  length strings all over, but we give them custom names,
  for example we define Password = String(128) because we
  use SHA-512 for passwords and need that length string to
  store them; TODO: does this really work?

- related to string lengths, how much space do we need to
  store network addresses? as long as we stay "numeric"
  the worst case is clear: an IPv6 address needs up to 39
  characters, e.g. "2001:0f68:0000:0000:0000:0000:1986:69af",
  if we add a port we need 6 more, e.g. ":27961", if we add
  a CIDR we need 4 more, e.g. "/101"; for a total of 49 or
  so characters; domain names are a bit more contentious
  again since very few people seem sure about the exact
  limits; we use Address = String(256) for now and we'll
  see if we ever need more

- we never delete anything; at most we mark things inactive
"""

from datetime import datetime
from hashlib import sha512

from sqlalchemy import Column, Sequence, ForeignKey
from sqlalchemy import Boolean, Integer, String, Text, DateTime
from sqlalchemy.orm import relationship, backref
from sqlalchemy.ext.declarative import declarative_base

GUID = Tiny = String(32)
Short = String(64)
Password = Medium = String(128)
Address = Long = String(256)

Base = declarative_base()

class Player(Base):
    """
    Player observed on a game server.

    - more information is available but recording the minimum should be
      enough for now

    - the "bad names" feature can be implemented without keeping score
      of how often someone was warned, but maybe we should add a field
      that can be used "open-ended" by other modules? actually, for bad
      names it doesn't matter since we record the bad name anyway, no
      way around it unless we filter them out *before* they hit the
      userinfo change - but then we'd have no record of them...
    """
    __tablename__ = 'players'

    id = Column(Integer, Sequence('players_ids'), nullable=False, unique=True)
    name = Column(Tiny, primary_key=True, nullable=False,
                  doc="ioq3 player name 20 chars")
    address = Column(Address, primary_key=True, doc="ip address")
    guid = Column(GUID, primary_key=True, doc="ioq3 GUID 32 chars")
    server = Column(Address, primary_key=True, doc="ip address")
    first = Column(DateTime, nullable=False, doc="on insert")
    last = Column(DateTime, nullable=False, doc="on insert and update")

    def __init__(self, name, address, guid, server):
        self.name = name
        self.address = address
        self.guid = guid
        self.server = server
        self.first = self.last = datetime.utcnow()

    def __repr__(self):
        return "Player<name: %s; address: %s; guid: %s; server: %s>" % (
            self.name, self.address, self.guid, self.server
        )

class User(Base):
    """
    User registered with the hub.

    TODO: only admins? only members? everybody?
    TODO: permission mechanism missing
    """
    __tablename__ = 'users'

    id = Column(Integer, Sequence('users_ids'), nullable=False, unique=True)
    login = Column(Tiny, primary_key=True)
    password = Column(Password, nullable=False, doc="sha512 hash")
    name = Column(Short, nullable=False, doc="full name")
    email = Column(Address, nullable=False, unique=True)
    activated = Column(Boolean, nullable=False, doc="activated, email valid")
    disabled = Column(Boolean, nullable=False, doc="disabled, can't login")
    first = Column(DateTime, nullable=True)
    last = Column(DateTime, nullable=True)

    def __init__(self, login, password, name, email, activated=False,
                 disabled=False):
        self.login = login
        self.password = sha512(password).hexdigest()
        self.name = name
        self.email = email
        self.activated = activated
        self.disabled = disabled

    def __repr__(self):
        return "User<login: %s; name: %s; email: %s; activated: %s>" % (
            self.login, self.name, self.email, self.activated
        )

class GameAdmin(Base):
    """
    Information for users who are game server admins.

    TODO: admins must configure clients for constant guids

    TODO: the "correct" design would be user --1:N--> ip --1:N--> guid
    to allow, for example, two admins with separate installs behind
    the same router and hence with the same ip; that avoids duplicating
    the ip, but I don't really think we need to care; do we? what we
    have here is much simpler...

    TODO: do we have cascade in the right place here? we usually
    don't delete anything anyway, but IF for some reason a user
    actually gets deleted, we wouldn't want useless game_admins
    to keep hanging around, correct?
    """
    __tablename__ = 'game_admins'

    id = Column(Integer, Sequence('game_admins_ids'), primary_key=True)
    address = Column(Address, nullable=False, doc="ip address")
    guid = Column(GUID, primary_key=True, doc="ioq3 GUID 32 chars")
    password = Column(Password, nullable=False, doc="sha512 hash")
    active = Column(Boolean, nullable=False)

    user_id = Column(Integer, ForeignKey('users.id'))

    user = relationship(
        User,
        backref=backref('game_admins', order_by=id),
        cascade="all, delete, delete-orphan",
        single_parent=True
    )

    def __init__(self, address, guid, password, active=False):
        self.address = address
        self.guid = guid
        self.password = sha512(password).hexdigest()
        self.active = active

    def __repr__(self):
        return "GameAdmin<user_name: %s; address: %s; guid: %s; active: %s>" % (
            self.user.name, self.address, self.guid, self.active
        )

class Server(Base):
    """
    Game server configured by administrator.

    TODO: server guid? really? and how?
    TODO: should be let users register servers? :-D
    """
    __tablename__ = 'servers'

    id = Column(Integer, Sequence('servers_ids'), nullable=False, unique=True)
    guid = Column(GUID, primary_key=True)
    address = Column(Address, primary_key=True)
    rcon = Column(Short, nullable=False)
    active = Column(Boolean, nullable=False)
    first = Column(DateTime, nullable=True)
    last = Column(DateTime, nullable=True)

    def __init__(self, guid, address, rcon, active=False):
        self.guid = guid
        self.address = address
        self.rcon = rcon
        self.active = active

    def __repr__(self):
        return "Server<guid: %s; address: %s; active: %s>" % (
            self.guid, self.address, self.active
        )

if __name__ == "__main__":
    p = Player("|ALPHA| CCCP", "1.2.3.4", "CCCPCCCPCCCPCCCPCCCPCCCPCCCPCCCP",
               "3.4.5.6:27964")
    print p
    p2 = Player("a", "b", "c", "d")
    print p2
    print p

    u = User("mad", "gagagagaga", "|ALPHA| Mad Professor",
             "alpha.mad.professor@gmail.com", True)
    print u
    print u.game_admins

    ga = GameAdmin("5.3.1.9", "MADMADMADMADMADMADMADMADMADMADMA",
                   "untzuntzuntzuntz", False)
    u.game_admins.append(ga)
    print u
    print u.game_admins
    print ga
    print ga.user

    s = Server("SERVERSERVERserverSERVERserverSE", "23.54.12.95",
               "illnevertellofcoursebutheyyourefreetotry", True)
    print s
