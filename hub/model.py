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
  systems; MySQL doesn't seem to like variable-length Text
  quite as much as SQLite; so we use fixed-length strings,
  but we give them custom names like Tiny and Password for
  consistency

- related to string lengths, how much space do we need to
  store network addresses? as long as we stay "numeric"
  the worst case is clear: an IPv6 address needs up to 39
  characters, e.g. "2001:0f68:0000:0000:0000:0000:1986:69af",
  if we add a port we need 6 more, e.g. ":27961", if we add
  a CIDR we need 4 more, e.g. "/101"; for a total of 49 or
  so characters; domain names are a bit more contentious
  again since very few people seem sure about the exact
  limits; we use the custom Address type for now and if we
  ever fail to store something important we'll revise it

- we never delete anything; at most we mark things inactive

- it's a major pain to get sqlalchemy to do something like
  autoincrement on non-primary keys portably across databases;
  the easiest workaround seems to be to make the ids primary
  keys even though we didn't intend them to be used as such
  for some tables; then add unique and index constraints on
  the composite keys we wanted to be primary originally; and
  we still have to use Sequence() to make some DBs happy...

- revision histories (for bans specifically):
  http://blog.mitechie.com/2010/01/18/auto-logging-to-sqlalchemy-and-turbogears-2/
  http://www.sqlalchemy.org/docs/examples.html#module-versioning
"""

from datetime import datetime
from hashlib import sha256

from sqlalchemy import Column, Sequence, ForeignKey
from sqlalchemy import Boolean, Integer, String, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base

GUID = Tiny = String(32)
Password = Short = String(64)
Medium = String(128)
Address = Long = String(256)

Base = declarative_base()

class Player(Base):
    """
    Player observed on a game server.

    - more information is available but recording the minimum should be
      enough; there are lots of these after all...

    - a more normalized approach would be to consider ip address the
      central focus and then foreign key that to separate tables for
      name, guid, and server; probably overkill, so we de-normalize

    - the "bad names" feature can be implemented without keeping score
      of how often someone was warned, but maybe we should add a field
      that can be used "open-ended" by other modules? actually, for bad
      names it doesn't matter since we record the bad name anyway, no
      way around it unless we filter them out *before* they hit the
      userinfo change - but then we'd have no record of them...
    """
    __tablename__ = 'players'
    __table_args__ = (UniqueConstraint('name', 'address', 'guid', 'server'), {})

    id = Column(Integer, Sequence('players_ids'), primary_key=True,
                autoincrement=True, nullable=False, unique=True)
    name = Column(Tiny, nullable=False, doc="ioq3 player name 20 chars")
    address = Column(Address, nullable=False, doc="ip address")
    guid = Column(GUID, nullable=False, doc="ioq3 GUID 32 chars")
    server = Column(Address, nullable=False, doc="ip address")
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

    id = Column(Integer, Sequence('users_ids'), primary_key=True,
                autoincrement=True, nullable=False, unique=True)
    login = Column(Tiny, nullable=False, unique=True)
    password = Column(Password, nullable=False, doc="hash")
    name = Column(Short, nullable=False, doc="full name")
    email = Column(Address, nullable=False, unique=True)
    activated = Column(Boolean, nullable=False, doc="activated, email valid")
    disabled = Column(Boolean, nullable=False, doc="disabled, can't login")
    created = Column(DateTime, nullable=False, doc="on insert")
    first = Column(DateTime, nullable=True, doc="first login")
    last = Column(DateTime, nullable=True, doc="last login")

    game_admins = relationship('GameAdmin', backref='user',
                               cascade='all, delete, delete-orphan')

    def __init__(self, login, password, name, email, activated=False,
                 disabled=False):
        self.login = login
        self.password = sha256(password).hexdigest()
        self.name = name
        self.email = email
        self.activated = activated
        self.disabled = disabled
        self.created = datetime.utcnow()

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
    __table_args__ = (UniqueConstraint('address', 'guid', 'password'), {})

    id = Column(Integer, Sequence('game_admins_ids'), primary_key=True,
                autoincrement=True, nullable=False, unique=True)
    address = Column(Address, nullable=False, doc="ip address")
    guid = Column(GUID, nullable=False, doc="ioq3 GUID 32 chars")
    password = Column(Password, nullable=False, doc="hash")
    created = Column(DateTime, nullable=False, doc="on insert")
    first = Column(DateTime, nullable=True, doc="first used in game")
    last = Column(DateTime, nullable=True, doc="last used in game")

    user_id = Column(Integer, ForeignKey('users.id'), nullable=False,
                     unique=False)

    def __init__(self, address, guid, password):
        self.address = address
        self.guid = guid
        self.password = sha256(password).hexdigest()
        self.created = datetime.utcnow()

    def __repr__(self):
        return "GameAdmin<user_name: %s; address: %s; guid: %s>" % (
            self.user.name, self.address, self.guid
        )

class Server(Base):
    """
    Game server configured by administrator.

    TODO: server guid? really? and how?
    TODO: should we let users register servers? :-D
    """
    __tablename__ = 'servers'
    __table_args__ = (UniqueConstraint('guid', 'address'), {})

    id = Column(Integer, Sequence('servers_ids'), primary_key=True,
                autoincrement=True, nullable=False, unique=True)
    guid = Column(GUID, nullable=False)
    address = Column(Address, nullable=False)
    rcon = Column(Short, nullable=False)
    active = Column(Boolean, nullable=False)
    created = Column(DateTime, nullable=False, doc="on insert")
    first = Column(DateTime, nullable=True, doc="first userinfo")
    last = Column(DateTime, nullable=True, doc="last userinfo")

    def __init__(self, guid, address, rcon, active=False):
        self.guid = guid
        self.address = address
        self.rcon = rcon
        self.active = active
        self.created = datetime.utcnow()

    def __repr__(self):
        return "Server<guid: %s; address: %s; active: %s>" % (
            self.guid, self.address, self.active
        )

class Ban(Base):
    """
    Ban of an address range.

    - uuid uniquely identifies ban, used in gossiping across
      hubs; TODO: should one ban have several uuids or not?
      right now several uuid are likely as utcnow() is used

    - store address and subnet range separately for faster
      range queries

    - who was banned is stored in player_bans, which assumes
      that we have a record for the player

    - who did the ban and why as well as the history of the
      ban over time is stored in history_bans

    - TODO: should the hub build a custom data structure for
      fast ban checks when it starts up?
    """
    __tablename__ = 'bans'

    id = Column(Integer, Sequence('bans_ids'), autoincrement=True,
                nullable=False, primary_key=True, unique=True)
    uuid = Column(Password, nullable=False, unique=True, doc="unique ban id")
    address = Column(Address, nullable=False, unique=True, doc="without CIDR")
    cidr = Column(Integer, nullable=False)
    active = Column(Boolean, nullable=False)

    def __init__(self, address, cidr, active=True):
        self.uuid = sha256("%s%s" % (datetime.utcnow(), address)).hexdigest()
        self.address = address
        self.cidr = cidr
        self.active = active

    def __repr__(self):
        return "Ban<uuid: %s; address: %s/%s; active: %s>" % (
            self.uuid, self.address, self.cidr, self.active
        )
