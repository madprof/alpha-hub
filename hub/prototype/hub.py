"""
A simple prototype for |ALPHA| Hub.

- receives UDP packets with userinfo strings
- echos them to other hubs
- parses them and logs important pieces in a database
"""

from socket import socket, AF_INET, SOCK_DGRAM
from sqlite3 import connect, PARSE_DECLTYPES, Row
from select import select
import logging
import hashlib
import os

# load the configuration file
HOST = None
SERVERS = None
HUBS = None
execfile(os.path.expanduser("~/.alphahub/config.py"))

def open_sockets():
    """
    Open all sockets.
    """
    IN = []
    for server, (port, _secret) in SERVERS.iteritems():
        sock = socket(AF_INET, SOCK_DGRAM)
        sock.bind((HOST, port))
        IN.append(sock)
    OUT = []
    for server, (port, _secret) in HUBS.iteritems():
        sock = socket(AF_INET, SOCK_DGRAM)
        sock.connect((server, port))
        OUT.append(sock)
    return (IN, OUT)

def close_sockets(IN, OUT):
    """
    Close all sockets.
    """
    for sock in IN:
        sock.close()
    for sock in OUT:
        sock.close()

def open_database(name):
    """
    Open database.
    """
    DB = connect(name, detect_types=PARSE_DECLTYPES)
    DB.row_factory = Row
    DB.text_factory = str
    return DB

def close_database(DB):
    """
    Close database.
    """
    DB.commit()
    DB.close()

def write_record(DB, name, ip, guid, server, port):
    """
    Write a player record to the database.

    If the record existing already, we fake an update
    to get "last" updated by the database trigger.
    """
    logging.info(
        "recording %s from ip %s with guid %s playing on %s:%s",
        name, ip, guid, server, port
    )
    results = DB.execute(
                  """SELECT * FROM Players WHERE
                     name=? AND ip=? AND guid=? AND server=? AND port=?""",
                  (name, ip, guid, server, port)
              ).fetchall()
    if len(results) == 0:
        DB.execute(
            """INSERT INTO Players (name, ip, guid, server, port)
               VALUES (?, ?, ?, ?, ?)""",
            (name, ip, guid, server, port)
        )
    else:
        DB.execute(
            """UPDATE Players SET guid=? WHERE
               name=? AND ip=? AND guid=? AND server=? AND port=?""",
            (guid, name, ip, guid, server, port)
        )
    DB.commit()

def parse_userinfo(userinfo):
    """
    Parse userinfo string into dictionary.
    """
    data = userinfo.split("\\")[1:]
    assert len(data) % 2 == 0
    keys = data[0::2]
    values = data[1::2]
    return dict(zip(keys, values))

def handle_userinfo(DB, host, port, data):
    """
    Handle a userinfo packet.

    Checks packet structure, MD4 checksum, etc. and eventually
    writes the player record. Returns false if we rejected the
    packet as invalid, true if we accepted it.
    """
    header, data = data[0:4], data[4:]
    if header != "\xff\xff\xff\xff":
        logging.debug("invalid packet header")
        return False

    md4, data = data.split("\n", 1) 
    if len(md4) != 32:
        logging.debug("invalid md4 length")
        return False

    secret = SERVERS[host][1]
    checksum = hashlib.new("md4", secret+"\n"+data).hexdigest()
    if md4 != checksum:
        logging.debug("invalid checksum (secrets probably don't match)")
        return False

    kind, data = data.split("\n", 1) 
    if kind != "userinfo":
        logging.debug("not a userinfo packet")
        return False

    var = parse_userinfo(data)
    write_record(DB, var["name"], var["ip"], var["cl_guid"], host, port)

    return True

def run(IN, OUT, DB):
    """
    Main loop, receiving packets from all our sockets
    and dispatching them.
    """
    while True:
        logging.debug("waiting in select")
        ready, _, _ = select(IN[:], [], [])
        for sock in ready:
            msg, (host, port) = sock.recvfrom(4096)
            logging.debug("received packet from %s:%s", host, port)
            if host not in SERVERS:
                logging.debug("host %s not in server list", host)
                continue
            if handle_userinfo(DB, host, port, msg):
                logging.debug("echoing packet from %s:%s", host, port)
                for out in OUT:
                    out.sendall(msg) # TODO: prefix original host:port?

def main():
    """
    Main program, set up logging and (mostly) log
    simple status messages.
    """
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logging.info("starting |ALPHA| Hub prototype")
    IN, OUT = open_sockets()
    logging.debug("bound and connected sockets")
    DB = open_database("hub.db")
    logging.debug("opened database")
    try:
        run(IN, OUT, DB)
    except Exception as exc:
        logging.exception("exception %s", exc)
    finally:
        logging.info("stopping |ALPHA| Hub prototype")
        close_database(DB)
        logging.debug("closed database")
        close_sockets(IN, OUT)
        logging.debug("closed sockets")

if __name__ == "__main__":
    main()
