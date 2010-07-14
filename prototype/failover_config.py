# put this into ~/.alphahub/failover_config.py and make sure it's not
# readable by anyone else (it contains passwords!)

# the host we run on and want to receive packets on; note
# that "localhost" is probably the wrong thing here, you
# want a host name that refers to an external network so you
# can receive packets from the outside

host = "host.ip.here"

# SQLite database file to use; eventually this will be a
# "real" database connection URL

database = "failover.db"
# the servers we listen to; for now each box has one port
# and secret on the hub, even if it runs multiple game
# servers; for a setup where one box runs games servers for
# multiple clans, this is not sufficient yet; note that host
# names are resolved to IPs and IPs must be unique; and yes,
# this is where sv_alphaFailoverHubHost and sv_alphaFailoverHubKey go

servers = {
    "server1.ip.addr": (27967, "somesecret"),
    "server2.ip.addr": (28202, "woootsecret")
}

# the hubs we listen to for packets that confirm userinfo
#it alreay has so failover can delete entries that are
#not needed; also we send packets to from the database that
#the hub(s) might not have;same restrictions as for
# game servers for now; we probably need more stuff here,
# rate limits, trust levels, and so on

hubs = {
    "hub.addr.1": (9534, "youcantknow"),
    "hub.ip.addr2": (2821, "thisissecret")
}
