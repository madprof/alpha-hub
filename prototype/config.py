# put this into ~/.alphahub/config.py and make sure it's not
# readable by anyone else (it contains passwords!)

# the host we run on and want to receive packets on; note
# that "localhost" is probably the wrong thing here, you
# want a host name that refers to an external network so you
# can receive packets from the outside

HOST = "the.hub.machine.tld"

# the servers we listen to; for now each box has one port
# and secret on the hub, even if it runs multiple game
# servers; for a setup where one box runs games servers for
# multiple clans, this is not sufficient yet; note that host
# names are resolved to IPs and IPs must be unique; and yes,
# this is where sv_alphaHubHost and sv_alphaHubKey go

SERVERS = {
    "some.game.server.tld": (42, "somesecret"),
    "some.other.game.tld": (543, "monkeyspam"),
}

# the hubs we listen to for gossip; same restrictions as for
# game servers for now; we probably need more stuff here,
# rate limits, trust levels, and so on

UPSTREAM = {
    "some.hub.server.tld": (9533, "youcantknow"),
}

# the hubs we send gossip to; same restrictions as for game
# servers for now; same notes as for upstream hubs apply

DOWNSTREAM = {
    "some.hub.server.tld": (453, "secretsofdoom"),
    "another.hub.tld": (12345, "itssofun"),
}

# TODO: should there be another level, i.e. hubs that we
# don't just gossip with but keep in sync with 100% (subject
# to the limitations of using UDP that is)? seems like a
# bad idea since it would lead to multiple sources of truth
# that don't necessarily agree
