-- creates sqlite database for hub.py prototype

CREATE TABLE Players (
    ip VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    guid VARCHAR NOT NULL,
    server VARCHAR NOT NULL,
    port VARCHAR NOT NULL,
    first TIMESTAMP,
    last TIMESTAMP,
    PRIMARY KEY (ip, name, guid, server, port)
);

CREATE TRIGGER insertPlayer AFTER INSERT ON Players
BEGIN
  UPDATE Players
    SET first = datetime("now")
      WHERE rowid = new.rowid;
  UPDATE Players
    SET last = datetime("now")
      WHERE rowid = new.rowid;
END;

CREATE TRIGGER updatePlayer AFTER UPDATE ON Players
BEGIN
  UPDATE Players
    SET last = datetime("now")
      WHERE rowid = new.rowid;
END;
