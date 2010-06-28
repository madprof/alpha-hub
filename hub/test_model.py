# |ALPHA| Hub - an authorization server for alpha-ioq3
# See files README and COPYING for copyright and licensing details.

"""
test_model.py - test the data model

- writing all this testing code is fairly tedious, but let's
  stick with the TDD program and see where it leads...

- both py.test and nose run setup_module() followed by all the
  tests, followed by teardown_module(); test functions run in
  order of appearance, but test methods run in ALPHABETICAL order!

- SQLite doesn't give a hoot about constraints like length of
  a string, so as long as we use it for testing we can't rely
  on the database complaining about all violations of the model

- MySQL can't even process our model without changes, neither
  PostgreSQL nor SQLite have any problem with it of course
"""

from datetime import datetime
from model import Ban, GameAdmin, Player, Server, User


class Global(object):
    """
    Global state for tests.
    """
    # factory class for sessions
    Session = None
    # engine we are connected to
    engine = None


def setup_module():
    """
    Prepare the test database.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from model import Base
    from py.test import config
    Global.engine = create_engine(config.getvalue("database"))
    Base.metadata.create_all(Global.engine)
    Global.Session = sessionmaker(bind=Global.engine)

def teardown_module():
    """
    Clean up the test database.
    """
    from model import Base
    from py.test import config
    if config.getvalue("nodrop"):
        return
    Base.metadata.drop_all(Global.engine)


class TestServers(object):
    """
    Server objects.
    TODO: failed objects/insertions/deletions?
    """
    def check_server(self, server, id, guid, address, rcon, active):
        assert server.id == id
        assert server.guid == guid
        assert server.address == address
        assert server.rcon == rcon
        assert server.active == active
        assert isinstance(server.created, datetime)
        assert server.created < datetime.utcnow()
        assert server.first is None or isinstance(server.first, datetime)
        assert server.last is None or isinstance(server.last, datetime)
        assert server.first <= server.last

    def test0_insert(self):
        servers = [
            Server("first server guid", "1.2.3.4", "some password", True),
            Server("second server guid", "2.3.4.5", "another pw", False),
            Server("anotherserverlongenoughtofillit!", "23.54.12.95",
                   "illnevertellofcoursebutheyyourefreetotrywhateverpassword",
                   True)
        ]
        session = Global.Session()
        for server in servers:
            session.add(server)
        session.commit()
        self.check_server(servers[1], 2, "second server guid", "2.3.4.5",
                          "another pw", False)
        session.close()

    def test1_select_before_delete(self):
        ids = [1, 2, 3]
        addresses = ["1.2.3.4", "2.3.4.5", "23.54.12.95"]
        session = Global.Session()
        assert session.query(Server).count() == 3
        i = 0
        for server in session.query(Server).order_by(Server.id):
            assert server.id == ids[i]
            assert server.address == addresses[i]
            i += 1
        session.close()

    def test2_delete(self):
        session = Global.Session()
        second = session.query(Server).filter(Server.id==2).one()
        session.delete(second)
        session.commit()
        session.close()

    def test3_select_after_delete(self):
        ids = [1, 3]
        addresses = ["1.2.3.4", "23.54.12.95"]
        session = Global.Session()
        assert session.query(Server).count() == 2
        i = 0
        for server in session.query(Server).order_by(Server.id):
            assert server.id == ids[i]
            assert server.address == addresses[i]
            i += 1
        session.close()


class TestPlayers(object):
    """
    Player objects.
    TODO: failed objects/insertions/deletions?
    """
    def check_player(self, player, id, name, address, guid, server):
        assert player.id == id
        assert player.name == name
        assert player.address == address
        assert player.guid == guid
        assert player.server == server
        assert player.first is None or isinstance(player.first, datetime)
        assert player.last is None or isinstance(player.last, datetime)
        assert player.first <= player.last

    def test0_insert(self):
        players = [
            Player("A", "1.2.3.4", "01234567890123456789012345678901",
                   "3.4.5.6:27964"),
            Player("B", "1.2.3.4", "01234567890123456789012345678901",
                   "3.4.5.6:27964"),
            Player("C", "1.2.3.4", "01234567890123456789012345678901",
                   "3.4.5.6:27964"),
            Player("D", "1.2.3.4", "01234567890123456789012345678901",
                   "3.4.5.6:27964"),
            Player("A", "1.7.3.4", "01234567890123456789012345678901",
                   "3.4.5.6:27964"),
        ]
        session = Global.Session()
        for player in players:
            session.add(player)
        session.commit()
        self.check_player(players[1], 2, "B", "1.2.3.4",
                          "01234567890123456789012345678901", "3.4.5.6:27964")
        for i in range(len(players)):
            assert i+1 == players[i].id
        for i in range(len(players)):
            assert players[i].first == players[i].last
        for i in range(len(players)-1):
            assert players[i].first < players[i+1].first
            assert players[i].last < players[i+1].last
        session.close()

    def test1_select_before_delete(self):
        ids = [1, 2, 3, 4, 5]
        names = ["A", "B", "C", "D", "A"]
        session = Global.Session()
        assert session.query(Player).count() == 5
        i = 0
        for player in session.query(Player).order_by(Player.id):
            assert player.id == ids[i]
            assert player.name == names[i]
            i += 1
        session.close()

    def test2_delete(self):
        session = Global.Session()
        player = session.query(Player).filter(Player.id==2).one()
        session.delete(player)
        player = session.query(Player).filter(Player.id==5).one()
        session.delete(player)
        session.commit()
        session.close()

    def test3_select_after_delete(self):
        ids = [1, 3, 4]
        names = ["A", "C", "D"]
        session = Global.Session()
        assert session.query(Player).count() == 3
        i = 0
        for player in session.query(Player).order_by(Player.id):
            assert player.id == ids[i]
            assert player.name == names[i]
            i += 1
        session.close()


class TestGoodObjects(object):
    """
    Create model objects and check consistency.
    """
    def test_Ban(self):
        b = Ban("72.34.121.50", 24)
        assert b.id is None
        assert len(b.uuid) == 64
        assert b.address == "72.34.121.50"
        assert b.cidr == 24
        assert b.active
    def test_GameAdmin(self):
        g = GameAdmin("5.3.1.9", "MADMADMADMADMADMADMADMADMADMADMA",
                      "untzuntzuntzuntz")
        assert g.id is None
        assert g.address == "5.3.1.9"
        assert g.guid == "MADMADMADMADMADMADMADMADMADMADMA"
        assert len(g.password) == 64
        assert isinstance(g.created, datetime)
        assert g.first is None
        assert g.last is None
        assert g.user is None
    def test_User(self):
        # TODO
        u = User("mad", "gagagagaga", "|ALPHA| Mad Professor",
                 "alpha.mad.professor@gmail.com", True, False)

def test_insert_game_admins():
    """
    Insert a user and a bunch of gameadmins.
    """
    session = Global.Session()

    u = User("mad", "gagagagaga", "|ALPHA| Mad Professor",
             "alpha.mad.professor@gmail.com", True, False)
    session.add(u)
    session.commit()
    assert len(u.game_admins) == 0

    ads = [
        GameAdmin("5.3.1.9", "MADMADMADMADMADMADMADMADMADMADMA", "untzuntzuntzuntz"),
        GameAdmin("2.3.1.9", "MADMADMADMADMADMADMADMADMADMADMA", "untzuntzuntzuntz"),
        GameAdmin("5.3.1.9", "SADSADSADMADMADMADSADMADMADMADMA", "untzuntzuntzuntz"),
    ]

    for a in ads:
        a.user = u
        session.add(a)

    session.commit()

    assert len(u.game_admins) == 3
    for i in range(len(ads)):
        assert ads[i] == u.game_admins[i]

    assert session.query(User).count() == 1
    assert session.query(GameAdmin).count() == 3

    session.delete(ads[2])
    session.commit()

    assert session.query(User).count() == 1
    assert session.query(GameAdmin).count() == 2

    session.delete(u)
    session.commit()

    assert session.query(User).count() == 0
    assert session.query(GameAdmin).count() == 0
