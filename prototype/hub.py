# |ALPHA| Hub - an authorization server for alpha-ioq3
# See files README and COPYING for copyright and licensing details.

"""
A simple prototype for |ALPHA| Hub.

- receives userinfo strings from game servers
- parses them and logs important pieces in a database
- gossips with other hubs
- logs gossip in a database
"""

# TODO: add "global" stuff to config as __private attributes
# to reduce number of parameters passed around?

# TODO: track thread-local database connections; use cleanup
# to interrupt() each, then close() it? may not be too nice,
# we'd have to call close() from the main thread OR we need
# to catch the interrupt-exception (and which one is that???)
# in the thread and close() there assuming that we'll die for
# sure since the main thread will exit; messy, messy, messy

import hashlib as HASH
import logging as L
import os as OS
import platform as PLAT
import select as SEL
import socket as S
import sqlite3 as SQL

import pool as POOL

def load_config(path):
    """
    Load configuration file from given path.

    Basic consistency checks, safe defaults for missing keys.
    """
    L.debug("loading config file '%s'", path)
    default = {
        'host': 'localhost',
        'database': 'hub.db',
        'servers': {},
        'listen': {},
        'tell': {},
        '__name': 'default',
    }
    config = {}
    if not OS.path.exists(path):
        L.error("config file '%s' not found", path)
        config = default
    else:
        execfile(path, globals(), config)
        config['__name'] = path
        validate_config(config, default)
        config['servers'] = resolve_config(config['servers'])
        config['listen'] = resolve_config(config['listen'])
        config['tell'] = resolve_config(config['tell'])
    L.debug("loaded config file '%s'", path)
    return config

def validate_config(config, default):
    """
    Validate config against default.
    """
    for section in default:
        if section not in config:
            L.error("config file '%s' has no section '%s'",
                    config['__name'], section)
            config[section] = default[section]
        if type(config[section]) is not type(default[section]):
            L.error("config file '%s' section '%s' has wrong format",
                    config['__name'], section)
            config[section] = default[section]

def resolve_config(section):
    """
    Resolve configured host names to IP addresses.

    We allow host names in the config file but want to avoid DNS queries
    in the main loop; so we convert all hostnames to IPs on startup.

    TODO: Support IPv6?
    """
    resolved = {}
    for server in section:
        try:
            ip = S.gethostbyname(server)
        except S.gaierror as exc:
            L.exception("failed to resolve %s because of %s",
                        server, exc)
            # TODO: could "continue" here to remove the whole
            # thing from the config? what's better?
            ip = server
        if ip != server:
            L.info("%s resolved to %s", server, ip)
            assert ip not in resolved # no duplicates!
            resolved[ip] = section[server]
        else:
            assert server not in resolved # no duplicates!
            resolved[server] = section[server]
    return resolved

def open_sockets(config):
    """
    Open all sockets.
    """
    host = config['host']
    servers = []
    for server, (port, _secret) in config['servers'].iteritems():
        sock = S.socket(S.AF_INET, S.SOCK_DGRAM)
        sock.bind((host, port))
        L.debug("bound socket %s for server %s", sock.getsockname(), server)
        servers.append(sock)
    listen = []
    for server, (port, _secret) in config['listen'].iteritems():
        sock = S.socket(S.AF_INET, S.SOCK_DGRAM)
        sock.bind((host, port))
        L.debug("bound socket %s for listen %s", sock.getsockname(), server)
        listen.append(sock)
    tell = []
    for server, (port, _secret) in config['tell'].iteritems():
        sock = S.socket(S.AF_INET, S.SOCK_DGRAM)
        sock.connect((server, port))
        L.debug("connected socket %s for tell %s",
                sock.getsockname(), sock.getpeername())
        tell.append(sock)
    return servers, listen, tell

def close_sockets(servers, listen, tell):
    """
    Close all sockets.
    """
    for sock in servers+listen+tell:
        L.debug("closing socket %s", sock.getsockname())
        sock.close()

def open_database(config):
    """Open database connection."""
    conn = SQL.connect(config['database'], timeout=16,
                       detect_types=SQL.PARSE_DECLTYPES)
    conn.row_factory = SQL.Row
    conn.text_factory = str
    conn.execute("PRAGMA foreign_keys = ON")
    foreign = conn.execute("PRAGMA foreign_keys").fetchall()
    assert len(foreign) == 1
    assert foreign[0][0] == 1
    L.debug("opened database '%s'", config['database'])
    return conn

def create_tables(conn):
    """Create database tables (unless they exist already)."""
    with open("hub.sql") as script_file:
        script = script_file.read()
        conn.executescript(script)
        # TODO: would love to detect if we actually created
        # tables here but can't due to sqlite3 interface?

def close_database(conn):
    """Close database connection."""
    conn.close()
    L.debug("closed database")

def write_player(database, name, ip, guid, server, port):
    """
    Write a player record to the database.

    If the record exists already, we fake an update
    to get "last" updated by the database trigger.
    """
    L.info(
        "recording %s from ip %s with guid %s playing on %s:%s",
        name, ip, guid, server, port
    )
    results = database.execute(
                  """SELECT * FROM Players WHERE
                     name=? AND ip=? AND guid=? AND server=? AND port=?""",
                  (name, ip, guid, server, port)
              ).fetchall()
    if len(results) == 0:
        database.execute(
            """INSERT INTO Players (name, ip, guid, server, port)
               VALUES (?, ?, ?, ?, ?)""",
            (name, ip, guid, server, port)
        )
    else:
        database.execute(
            """UPDATE Players SET guid=? WHERE
               name=? AND ip=? AND guid=? AND server=? AND port=?""",
            (guid, name, ip, guid, server, port)
        )
    database.commit()

def write_gossip(database, name, ip, guid, server, port, origin):
    """
    Write a gossip record to the database.

    If the record exists already, we fake an update
    to get "last" and "count" updated by the database trigger.
    """
    L.info(
        "gossip from %s: recording %s from ip %s with guid %s playing on %s:%s",
        origin, name, ip, guid, server, port
    )
    results = database.execute(
                  """SELECT * FROM Gossips WHERE
                     name=? AND ip=? AND guid=? AND server=? AND port=? AND
                     origin=?""",
                  (name, ip, guid, server, port, origin)
              ).fetchall()
    if len(results) == 0:
        database.execute(
            """INSERT INTO Gossips (name, ip, guid, server, port, origin)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (name, ip, guid, server, port, origin)
        )
    else:
        database.execute(
            """UPDATE Gossips SET guid=? WHERE
               name=? AND ip=? AND guid=? AND server=? AND port=? AND
               origin=?""",
            (guid, name, ip, guid, server, port, origin)
        )
    database.commit()

def parse_userinfo(userinfo):
    """
    Parse userinfo string into dictionary.
    """
    data = userinfo.split("\\")[1:]
    assert len(data) % 2 == 0
    keys = data[0::2]
    values = data[1::2]
    return dict(zip(keys, values))

def handle_userinfo(config, database, tell, host, port, data):
    """
    Handle a userinfo packet.

    Checks packet structure, MD4 checksum, etc. and eventually
    writes the player record.
    """
    header, data = data[0:4], data[4:]
    if header != '\xff\xff\xff\xff':
        L.debug("invalid packet header")
        return

    md4, data = data.split('\n', 1)
    if len(md4) != 32:
        L.debug("invalid md4 length")
        return

    secret = config['servers'][host][1]
    checksum = HASH.new('md4', secret+'\n'+data).hexdigest()
    if md4 != checksum:
        L.debug("invalid checksum (secrets probably don't match)")
        return

    kind, data = data.split('\n', 1)
    if kind != 'userinfo':
        L.debug("not a userinfo packet")
        return

    var = parse_userinfo(data)
    write_player(database, var['name'], var['ip'], var['cl_guid'], host, port)
    if len(tell) > 0:
        echo_tell(config, tell, host, port, var)

def echo_tell(config, tell, host, port, var):
    """
    Send gossip to tell hubs.
    """
    L.debug("echoing packet from %s:%s...", host, port)
    payload = 'gossip player\n\\server\\%s:%s\\name\\%s\\ip\\%s\\guid\\%s' % (
        host, port, var['name'], var['ip'], var['cl_guid'])
    for out in tell:
        L.debug("...to tell %s", out.getpeername())
        secret = config['tell'][out.getpeername()[0]][1]
        md4 = HASH.new('md4', secret+'\n'+payload).hexdigest()
        packet = md4+'\n'+payload
        try:
            # NOTE: using out.send(packet) will fail too if the other
            # side is not there; strange since the docs say it should
            # just keep on truckin'
            out.sendall(packet)
        except S.error as exc:
            L.warning("...sendall() failed with %s for %s", exc,
                      out.getpeername())

def handle_gossip(config, database, host, port, data):
    """
    Handle a gossip packet.

    Checks packet structure, MD4 checksum, etc. and eventually
    writes the gossip record.
    """
    md4, data = data.split('\n', 1)
    if len(md4) != 32:
        L.debug("invalid md4 length")
        return

    secret = config['listen'][host][1]
    checksum = HASH.new('md4', secret+'\n'+data).hexdigest()
    if md4 != checksum:
        L.debug("invalid checksum (secrets probably don't match)")
        return

    kind, data = data.split('\n', 1)
    if kind != 'gossip player':
        L.debug("not a gossip player packet")
        return

    var = parse_userinfo(data)
    origin = '%s:%s' % (host, port)
    host, port = var['server'].split(':')
    write_gossip(database, var['name'], var['ip'], var['guid'], host, port,
                 origin)

def handle_packet(packet, host, port, _tp_local):
    """Examine a packet and figure out what to do."""
    loc = _tp_local
    if host in loc.config['servers']:
        L.debug("processing server packet from %s:%s", host, port)
        handle_userinfo(loc.config, loc.database, loc.tell, host, port, packet)
    elif host in loc.config['listen']:
        L.debug("processing listen packet from %s:%s", host, port)
        handle_gossip(loc.config, loc.database, host, port, packet)
    else:
        L.debug("ignored spurious packet from %s:%s", host, port)

def run(config, servers, listen, tell):
    """
    Receive and handle packets from all our sockets.
    """
    def thread_open_database(local):
        """Helper to create thread-local storage."""
        local.database = open_database(config)
        local.config = config
        local.servers = servers
        local.listen = listen
        local.tell = tell

    pool = POOL.ThreadPool(init_local=thread_open_database)
    while True:
        L.debug("sleeping in select")
        ready, _, _ = SEL.select(servers+listen, [], [])
        L.debug("woke up for %s socket(s)", len(ready))
        for sock in ready:
            # TODO: could pass sock to thread and read there, but
            # what are the implications of going back into select
            # while another thread could still be reading? seems
            # safer to just read here (although that costs time)
            # and put the handling off into a thread instead
            packet, (host, port) = sock.recvfrom(4096)
            L.debug("received packet from %s:%s", host, port)
            pool.add(handle_packet, packet, host, port)

def safe_run(config, servers, listen, tell):
    """
    Wrapper around run() to catch exceptions.
    """
    try:
        run(config, servers, listen, tell)
    except BaseException as exc:
        L.exception("terminated by exception %s", exc)

def main():
    """
    Main program.

    Load config, setup, and teardown.
    """
    L.info("starting |ALPHA| Hub prototype")
    config_path = {
        'Linux': '~/.alphahub/config.py',
        'Windows': '~/alphahub/config.py',
    }[PLAT.system()]
    config = load_config(OS.path.expanduser(config_path))
    servers, listen, tell = open_sockets(config)
    L.debug("bound and connected all sockets")
    database = open_database(config)
    create_tables(database)
    safe_run(config, servers, listen, tell)
    L.info("stopping |ALPHA| Hub prototype")
    close_database(database)
    close_sockets(servers, listen, tell)
    L.debug("closed all sockets")

if __name__ == "__main__":
    L.basicConfig(
        level=L.DEBUG,
        format="%(asctime)s - %(threadName)s - %(levelname)s - %(message)s"
    )
    main()
