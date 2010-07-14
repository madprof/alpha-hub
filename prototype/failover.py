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
        'database': 'failover.db',
        'servers': {},
        'hubs': {},
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
        config['hubs'] = resolve_config(config['hubs'])
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
        srv_ip = S.gethostbyname(server)
        if srv_ip != server:
            L.info("%s resolved to %s", server, srv_ip)
            assert srv_ip not in resolved # no duplicates!
            resolved[srv_ip] = section[server]
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
    hubs = []
    for server, (port, _secret) in config['hubs'].iteritems():
        sock = S.socket(S.AF_INET, S.SOCK_DGRAM)
        sock.bind((host, port))
        L.debug("bound socket %s for hub %s", sock.getsockname(), server)
        hubs.append(sock)
    return servers, hubs

def close_sockets(servers, hubs):
    """
    Close all sockets.
    """
    for sock in servers+hubs:
        L.debug("closing socket %s", sock.getsockname())
        sock.close()

def open_database(config):
    """Open database connection."""
    conn = SQL.connect(config['database'], timeout=16,
                       detect_types=SQL.PARSE_DECLTYPES)
    conn.row_factory = SQL.Row
    conn.text_factory = str
    L.debug("opened database '%s'", config['database'])
    return conn

def create_tables(conn):
    """Create database tables (unless they exist already)."""
    with open("failover.sql") as script_file:
        script = script_file.read()
        conn.executescript(script)
        # TODO: would love to detect if we actually created
        # tables here but can't due to sqlite3 interface?

def close_database(conn):
    """Close database connection."""
    conn.close()
    L.debug("closed database")

def get_db_entries(conn):
    """Get current database entries for failover."""
    results = conn.execute("""SELECT 'rowid','server','port','packet', 'time'
                           FROM failover""").fetchall()
    return results

def del_db_entry(conn, rowid):
    """Delete entry from failover database"""
    conn.execute("""delete from failover where `rowid`=?""", (rowid))
    conn.commit()
    
def write_packet(database, server, port, userinfo):
    """
    Write a player record to the database.

    If the record exists already, we fake an update
    to get "last" updated by the database trigger.
    """
    L.info(
        "recording Packet from %s:%s containing: %s",
        server, port, userinfo
    )
    database.execute(
        """INSERT INTO failover (server, port, packet)
           VALUES (?, ?, ?)""",
           (server, port, userinfo)
    )
    database.commit()

def echo_to_hubs(config, rowid, hubs, host, packet):
    """
    Send gossip to tell hubs.
    """
    L.debug("Sending Database Userinfo packet from %s to hubs ...",
            host)
    payload = 'failover player\n\\rowid\\%i\\server\\%s\\time\\%s\n%s' % (
        rowid, host, packet[1], packet[0])
    for out in hubs:
        L.debug("...to hub %s", out.getpeername())
        secret = config['hubs'][out.getpeername()[0]][1]
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

def handle_hub(config, database, host, data):
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

    secret = config['hubs'][host][1]
    checksum = HASH.new('md4', secret+'\n'+data).hexdigest()
    if md4 != checksum:
        L.debug("invalid checksum (secrets probably don't match)")
        return

    kind, data = data.split('\n', 1)
    if kind != 'got failover player':
        L.debug("not a gossip player packet")
        return
    del_db_entry(database, data.strip())

def handle_packet(packet, host, port, _tp_local):
    """Examine a packet and figure out what to do."""
    loc = _tp_local
    if host in loc.config['servers']:
        L.debug("processing server packet from %s:%s", host, port)
        write_packet(loc.database, host, port, packet)
    elif host in loc.config['hubs']:
        L.debug("processing hub packet from %s:%s", host, port)
        handle_hub(loc.config, loc.database, host, packet)
    else:
        L.debug("ignored spurious packet from %s:%s", host, port)

def run(config, servers, hubs):
    """
    Receive and handle packets from all our sockets.
    """
    def thread_open_database(local):
        """Helper to create thread-local storage."""
        local.database = open_database(config)
        local.config = config
        local.servers = servers
        local.hubs = hubs
    pool = POOL.ThreadPool(init_local=thread_open_database)
    while True:
        L.debug("sleeping in select")
        ready, _, _ = SEL.select(servers+hubs, [], [], 5)
        print ready
        if ready == []:
            database = open_database(config)
            for ent in get_db_entries(database):
                source_server = '%i:%i' % (ent[1], ent[2])
                echo_to_hubs(config,
                             ent[0],
                             hubs,
                             source_server,
                             (ent[3], ent[4])
                             )
            close_database(database)
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
        

def safe_run(config, servers, hubs):
    """
    Wrapper around run() to catch exceptions.
    """
    try:
        run(config, servers, hubs)
    except BaseException as exc:
        L.exception("terminated by exception %s", exc)

def main():
    """
    Main program.

    Load config, setup, and teardown.
    """
    L.info("starting |ALPHA| Failover Hub prototype")
    config_path = {
        'Linux': '~/.alphahub/failover_config.py',
        'Windows': '~/alphahub/failover_config.py',
    }[PLAT.system()]
    config = load_config(OS.path.expanduser(config_path))
    servers, hubs = open_sockets(config)
    L.debug("bound and connected all sockets")
    database = open_database(config)
    create_tables(database)
    safe_run(config, servers, hubs)
    L.info("stopping |ALPHA| Failover Hub prototype")
    close_database(database)
    close_sockets(servers, hubs)
    L.debug("closed all sockets")

if __name__ == "__main__":
    L.basicConfig(
        level=L.DEBUG,
        format="%(asctime)s - %(threadName)s - %(levelname)s - %(message)s"
    )
    main()
