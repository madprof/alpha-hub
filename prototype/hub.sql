-- |ALPHA| Hub - an authorization server for alpha-ioq3
-- See files README and COPYING for copyright and licensing details.

-- create sqlite database for |ALPHA| Hub prototype

BEGIN TRANSACTION;

-- actual players from game servers we run and trust
CREATE TABLE IF NOT EXISTS Players (
    ip VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    guid VARCHAR NOT NULL,
    server VARCHAR NOT NULL,
    port VARCHAR NOT NULL,
    first TIMESTAMP DEFAULT NULL,
    last TIMESTAMP DEFAULT NULL,
    PRIMARY KEY (ip, name, guid, server, port)
);

CREATE TRIGGER IF NOT EXISTS insertPlayer AFTER INSERT ON Players
BEGIN
  UPDATE Players
    SET first = datetime("now"), last = datetime("now")
      WHERE rowid = new.rowid;
END;

CREATE TRIGGER IF NOT EXISTS updatePlayer AFTER UPDATE ON Players
BEGIN
  UPDATE Players
    SET last = datetime("now")
      WHERE rowid = new.rowid;
END;

-- gossip from other hubs we keep only for reference
CREATE TABLE IF NOT EXISTS Gossips (
    ip VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    guid VARCHAR NOT NULL,
    server VARCHAR NOT NULL,
    port VARCHAR NOT NULL,
    origin VARCHAR NOT NULL,
    count INTEGER DEFAULT NULL,
    first TIMESTAMP DEFAULT NULL,
    last TIMESTAMP DEFAULT NULL,
    PRIMARY KEY (ip, name, guid, server, port, origin)
);

CREATE TRIGGER IF NOT EXISTS insertGossip AFTER INSERT ON Gossips
BEGIN
  UPDATE Gossips
    SET first = datetime("now"), last = datetime("now"), count = 0
      WHERE rowid = new.rowid;
END;

CREATE TRIGGER IF NOT EXISTS updateGossip AFTER UPDATE ON Gossips
BEGIN
  UPDATE Gossips
    SET last = datetime("now"),
        count = (SELECT count FROM Gossips WHERE rowid = new.rowid)+1
      WHERE rowid = new.rowid;
END;

COMMIT;
