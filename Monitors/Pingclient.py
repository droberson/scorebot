#!/usr/bin/env python2

import os
import re
import sys

from twisted.internet import reactor, protocol
from twisted.internet.defer import Deferred


def which(progname):
    """Search $PATH for the location of progname

    Args:
        progname (str) - program to search for.

    Returns:
        str containing location of binary on success.
        None if it is not found in $PATH
    """
    for directory in os.getenv("PATH").split(":"):
        current = directory + "/" + progname
        if os.path.isfile(current):
            return current
    return None

class PingProtocol(protocol.ProcessProtocol):

    def __init__(self, job, count=str(5)):
        self.job = job
        self.ipaddr = self.job.get_ip()
        self.data = ""
        self.received_re = re.compile("(\d) received")
        self.transmitted_re = re.compile("(\d) packets transmitted")
        self.recv = 0
        self.fail = 0
        self.trans = 0
        self.lost = 0
        self.ratio = 0
        self.d = Deferred()
        self.count = count
        self.ping_prog = which("ping")
        if self.ping_prog == None:
            sys.stderr.write("FATAL: ping not found in $PATH. Exiting")
            os._exit(os.EX_USAGE)

    def ping(self):
        reactor.spawnProcess(self, self.ping_prog, [self.ping_prog, "-c", self.count, self.ipaddr])

    def getDeferred(self):
        return self.d

    def outReceived(self, data):
        self.data += data

    def outConnectionLost(self):
        self.recv = int(self.received_re.search(self.data).group(1))
        self.trans = int(self.transmitted_re.search(self.data).group(1))
        self.lost = self.trans - self.recv
        self.job.set_ping_sent(self.trans)
        self.job.set_ping_respond(self.recv)
        self.ratio = self.recv / self.trans
        if 0 <= self.ratio <= 100:
            self.d.callback(self)
        else:
            self.d.errback()

    def get_recv(self):
        return self.recv

    def get_lost(self):
        return self.lost

