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


class TestUsers(object):
    """
    User objects.
    TODO: failed objects/insertions/deletions?
    """
    def check_user(self, user, id, login, password, name, email, activated,
                   disabled):
        from hashlib import sha256
        assert user.id == id
        assert user.login == login
        assert user.password == sha256(password).hexdigest()
        assert user.name == name
        assert user.email == email
        assert user.activated == activated
        assert user.disabled == disabled
        assert user.created < datetime.utcnow()
        assert user.first is None or isinstance(user.first, datetime)
        assert user.last is None or isinstance(user.last, datetime)
        assert user.first <= user.last
        assert isinstance(user.game_admins, list)

    def test0_insert(self):
        users = [
            User("girt", "ihateindianfood", "|ALPHA| Girt",
                 "girtbeefrobe@gmail.com", False, False),
            User("mad", "gagagagaga", "|ALPHA| Mad Professor",
                 "alpha.mad.professor@gmail.com", True, False),
            User("mission", "bmwsrmylife", "|ALPHA| Mission",
                 "dejgaming@gmail.com", True, False),
            User("slayer", "isuck", "RunSlayerPropaneAmuk",
                 "ass@wipe.flush", False, False)
        ]
        session = Global.Session()
        for user in users:
            session.add(user)
        session.commit()
        self.check_user(users[1], 2, "mad", "gagagagaga",
                        "|ALPHA| Mad Professor",
                        "alpha.mad.professor@gmail.com", True, False)
        for i in range(len(users)):
            assert i+1 == users[i].id
        session.close()

    def test1_select_before_delete(self):
        ids = [1, 2, 3, 4]
        logins = ["girt", "mad", "mission", "slayer"]
        session = Global.Session()
        assert session.query(User).count() == 4
        i = 0
        for user in session.query(User).order_by(User.id):
            assert user.id == ids[i]
            assert user.login == logins[i]
            i += 1
        session.close()

    def test2_delete(self):
        session = Global.Session()
        user = session.query(User).filter(User.id==4).one()
        session.delete(user)
        session.commit()
        session.close()

    def test3_select_after_delete(self):
        ids = [1, 2, 3]
        logins = ["girt", "mad", "mission"]
        session = Global.Session()
        assert session.query(User).count() == 3
        i = 0
        for user in session.query(User).order_by(User.id):
            assert user.id == ids[i]
            assert user.login == logins[i]
            i += 1
        session.close()


class TestGameAdmins(object):
    """
    GameAdmin objects.
    TODO: failed objects/insertions/deletions?
    """
    def check_gameadmin(self, gameadmin, user, id, address, guid, password):
        from hashlib import sha256
        assert gameadmin.id == id
        assert gameadmin.address == address
        assert gameadmin.guid == guid
        assert gameadmin.password == sha256(password).hexdigest()
        assert gameadmin.created < datetime.utcnow()
        assert gameadmin.first is None or isinstance(user.first, datetime)
        assert gameadmin.last is None or isinstance(user.last, datetime)
        assert gameadmin.first <= user.last
        assert gameadmin.user_id == user.id

    def test0_insert(self):
        session = Global.Session()
        # TODO: works if we load the users here
        mad = session.query(User).filter(User.id==2).one()
        girt = session.query(User).filter(User.id==1).one()
        gameadmins = [
            GameAdmin("5.3.1.9", "MADMADMADMADMADMADMADMADMADMADMA",
                      "untzuntzuntzuntz"),
            GameAdmin("5.3.3.9", "MADMADMADMADMADMADMADMADMADMADMA",
                      "untzuntzuntzuntz"),
            GameAdmin("5.3.1.9", "SADSADSADSADSADSADSADSADSADSADSA",
                      "untzuntzuntzuntz")
        ]
        for gameadmin in gameadmins:
            session.add(gameadmin)
        # TODO: but doesn't work if we load them here?
        gameadmins[0].user = mad
        gameadmins[1].user = mad
        gameadmins[2].user = girt
        # TODO: can't use the following instead? i thought it's symmetric?
#        mad.game_admins.append(gameadmins[0])
#        mad.game_admins.append(gameadmins[1])
#        girt.game_admins.append(gameadmins[2])
        session.commit()
        self.check_gameadmin(gameadmins[0], mad, 1, "5.3.1.9",
                             "MADMADMADMADMADMADMADMADMADMADMA",
                             "untzuntzuntzuntz")
        self.check_gameadmin(gameadmins[1], mad, 2, "5.3.3.9",
                             "MADMADMADMADMADMADMADMADMADMADMA",
                             "untzuntzuntzuntz")
        self.check_gameadmin(gameadmins[2], girt, 3, "5.3.1.9",
                             "SADSADSADSADSADSADSADSADSADSADSA",
                             "untzuntzuntzuntz")
        for i in range(len(gameadmins)):
            assert i+1 == gameadmins[i].id
        session.close()

    def test1_select_before_delete(self):
        ids = [1, 2, 3]
        addresses = ["5.3.1.9", "5.3.3.9", "5.3.1.9"]
        session = Global.Session()
        assert session.query(User).count() == 3
        assert session.query(GameAdmin).count() == 3
        i = 0
        for gameadmin in session.query(GameAdmin).order_by(GameAdmin.id):
            assert gameadmin.id == ids[i]
            assert gameadmin.address == addresses[i]
            i += 1
        session.close()

    def test2_delete(self):
        session = Global.Session()
        gameadmin = session.query(GameAdmin).filter(GameAdmin.id==1).one()
        session.delete(gameadmin)
        session.commit()
        user = session.query(User).filter(User.login=="girt").one()
        session.delete(user)
        session.commit()
        session.close()

    def test3_select_after_delete(self):
        session = Global.Session()
        assert session.query(User).count() == 2
        assert session.query(GameAdmin).count() == 1
        gameadmin = session.query(GameAdmin).one()
        assert gameadmin.id == 2
        assert gameadmin.address == "5.3.3.9"
        session.close()
