# |ALPHA| Hub - an authorization server for alpha-ioq3
# See files README and COPYING for copyright and licensing details.

"""
model.py - data model

- model classes perform important conversion on data handed to
  them in the constructor; see "password" for User for example
- all times are UTC in the database; convert at UI if necessary
- we never delete anything; at most we mark things inactive
- an IPv6 address is up to 39 characters long in the usual char
  format, e.g. "2001:0f68:0000:0000:0000:0000:1986:69af"; if
  we add a port, we need six more characters, e.g. ":27961";
  if we add a CIDR, we need four more chars, e.g. "/101"; so
  we need a total of 49 chars in the worst case; round up and
  you get 64 :-) domain names are a whole different can of
  worms, but I think 255 for FQDN + 6 for port would be enough;
  probably easiest to simply store either as an arbitrary length
  string, just in case...
"""

from datetime import datetime
from hashlib import sha512

from sqlalchemy import Column, Sequence
from sqlalchemy import Boolean, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Player(Base):
    """
    Player observed on a game server.
    """
    __tablename__ = 'players'

    id = Column(Integer, Sequence('players_id_sequence'), nullable=False,
                unique=True)
    name = Column(String(64), primary_key=True)
    address = Column(Text, primary_key=True)
    guid = Column(String(64), primary_key=True)
    server = Column(String(64), primary_key=True)
    first = Column(DateTime, nullable=False)
    last = Column(DateTime, nullable=False)

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

    TODO: activating an account to verify email versus disabling an account
    """
    __tablename__ = 'users'

    id = Column(Integer, Sequence('users_id_sequence'), nullable=False,
                unique=True)
    login = Column(String(64), primary_key=True)
    password = Column(String(128), nullable=False)
    name = Column(String(64), nullable=False)
    email = Column(String(128), nullable=False, unique=True)
    active = Column(Boolean, nullable=False)
    first = Column(DateTime, nullable=True)
    last = Column(DateTime, nullable=True)

    def __init__(self, login, password, name, email, active=False):
        self.login = login
        self.password = sha512(password).hexdigest()
        self.name = name
        self.email = email
        self.active = active

    def __repr__(self):
        return "User<login: %s; name: %s; email: %s; active: %s>" % (
            self.login, self.name, self.email, self.active
        )

class Server(Base):
    """
    Game server configured by administrator.

    TODO: server guid? really? and how?
    TODO: should be let users register servers? :-D
    """
    __tablename__ = 'servers'

    id = Column(Integer, Sequence('servers_id_sequence'), nullable=False,
                unique=True)
    guid = Column(String(64), primary_key=True)
    address = Column(Text, primary_key=True)
    rcon = Column(String(64), nullable=False)
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
