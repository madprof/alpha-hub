# put this into ~/.alphahub/config.py and make sure it's
# not readable by anyone else (it contains passwords!)

# the host we run on and want to receive packets on; note
# that "localhost" is probably the wrong thing here, you
# want your actual host name here so the sockets bind the
# right way and receive packets from the outside

HOST = "the.hub.machine.tld"

# the servers we listen to; for now each server can just
# have one port and secret key on the hub even if it runs
# multiple game servers; not sure if we need to allow more
# than that yet :-/

SERVERS = {
    "some.game.server.tld": (42, "somesecret"),
    "some.other.game.tld": (543, "monkeyspam"),
}

# the other hubs we echo to; note that we don't yet change
# the packets in any way, so they'll look like they really
# come from us; not good, but we'll need to define a new
# packet format for forwarded userinfo strings first, then
# we can fix this :-/

HUBS = {
    "some.hub.server.tld": (84, "anothersecret"),
}
