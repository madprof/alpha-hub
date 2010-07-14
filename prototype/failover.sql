-- |ALPHA| Failover Hub - a backup authorization server for alpha-ioq3
-- See files README and COPYING for copyright and licensing details.

-- create sqlite database for |ALPHA| Failover Hub prototype

BEGIN TRANSACTION;

-- actual packets from game servers we run and trust
CREATE TABLE IF NOT EXISTS failover (
    server VARCHAR NOT NULL,
    port VARCHAR NOT NULL,
    packet VARCHAR NOT NULL,
    time TIMESTAMP DEFAULT NULL
);

CREATE TRIGGER IF NOT EXISTS insertPacket AFTER INSERT ON failover
BEGIN
  UPDATE failover
    SET time = datetime("now")
      WHERE rowid = new.rowid;
END;

COMMIT;
