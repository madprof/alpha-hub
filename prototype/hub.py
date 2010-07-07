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

import hashlib as HASH
import logging as L
import os as OS
import platform as PLAT
import select as SEL
import socket as S
import sqlite3 as SQL

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
        'upstream': {},
        'downstream': {},
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
        config['upstream'] = resolve_config(config['upstream'])
        config['downstream'] = resolve_config(config['downstream'])
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
        ip = S.gethostbyname(server)
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
    upstream = []
    for server, (port, _secret) in config['upstream'].iteritems():
        sock = S.socket(S.AF_INET, S.SOCK_DGRAM)
        sock.bind((host, port))
        L.debug("bound socket %s for upstream %s", sock.getsockname(), server)
        upstream.append(sock)
    downstream = []
    for server, (port, _secret) in config['downstream'].iteritems():
        sock = S.socket(S.AF_INET, S.SOCK_DGRAM)
        sock.connect((server, port))
        L.debug("connected socket %s for downstream %s",
                sock.getsockname(), sock.getpeername())
        downstream.append(sock)
    return servers, upstream, downstream

def close_sockets(servers, upstream, downstream):
    """
    Close all sockets.
    """
    for sock in servers+upstream+downstream:
        L.debug("closing socket %s", sock.getsockname())
        sock.close()

def open_database(config):
    """
    Open database.
    """
    conn = SQL.connect(config['database'], detect_types=SQL.PARSE_DECLTYPES)
    conn.row_factory = SQL.Row
    conn.text_factory = str
    with open("hub.sql") as script_file:
        script = script_file.read()
        conn.executescript(script)
        # TODO: would love to detect if we created a new database
        # here but can't due to sqlite interface limitations?
    L.debug("opened database '%s'", config['database'])
    return conn

def close_database(conn):
    """
    Close database.
    """
    conn.commit()
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

def handle_userinfo(config, database, downstream, host, port, data):
    """
    Handle a userinfo packet.

    Checks packet structure, MD4 checksum, etc. and eventually
    writes the player record. Returns false if we rejected the
    packet as invalid, true if we accepted it.
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
    if len(downstream) > 0:
        echo_downstream(config, downstream, host, port, var)

def echo_downstream(config, downstream, host, port, var):
    """
    Send gossip to downstream hubs.
    """
    L.debug("echoing packet from %s:%s...", host, port)
    payload = 'gossip player\n\\server\\%s:%s\\name\\%s\\ip\\%s\\guid\\%s' % (
        host, port, var['name'], var['ip'], var['cl_guid'])
    for out in downstream:
        L.debug("...to downstream %s", out.getpeername())
        secret = config['downstream'][out.getpeername()[0]][1]
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
    writes the gossip record. Returns false if we rejected the
    packet as invalid, true if we accepted it.
    """
    md4, data = data.split('\n', 1)
    if len(md4) != 32:
        L.debug("invalid md4 length")
        return

    secret = config['upstream'][host][1]
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

def run(config, servers, upstream, downstream, database):
    """
    Receive and handle packets from all our sockets.
    """
    while True:
        L.debug("sleeping in select")
        ready, _, _ = SEL.select(servers+upstream, [], [])
        L.debug("woke up for %s socket(s)", len(ready))
        for sock in ready:
            packet, (host, port) = sock.recvfrom(4096)
            L.debug("received packet from %s:%s", host, port)
            if host in config['servers']:
                L.debug("processing server packet from %s:%s", host, port)
                handle_userinfo(config, database, downstream, host, port,
                                packet)
            elif host in config['upstream']:
                L.debug("processing upstream packet from %s:%s", host,
                              port)
                handle_gossip(config, database, host, port, packet)
            else:
                L.debug("ignored spurious packet from %s:%s", host, port)

def safe_run(config, servers, upstream, downstream, database):
    """
    Wrapper around run() to catch exceptions.
    """
    try:
        run(config, servers, upstream, downstream, database)
    except Exception as exc:
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
    servers, upstream, downstream = open_sockets(config)
    L.debug("bound and connected all sockets")
    database = open_database(config)
    safe_run(config, servers, upstream, downstream, database)
    L.info("stopping |ALPHA| Hub prototype")
    close_database(database)
    close_sockets(servers, upstream, downstream)
    L.debug("closed all sockets")

if __name__ == "__main__":
    L.basicConfig(level=L.DEBUG,
                  format="%(asctime)s - %(levelname)s - %(message)s")
    main()
