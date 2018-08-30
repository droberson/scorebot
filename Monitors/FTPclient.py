#!/usr/bin/env python2

"""FTPclient.py"""

import sys
import string

from io import BytesIO

from twisted.protocols.ftp import FTPClient, FTPClientBasic
from twisted.internet.protocol import Protocol, ClientCreator
from twisted.python.failure import Failure
from twisted.internet import reactor


class BufferingProtocol(Protocol):
    """Simple utility class that holds all data written to it in a buffer."""
    def __init__(self):
        self.buffer = BytesIO()

    def dataReceived(self, data):
        self.buffer.write(data)


# TODO ???
class CTFFTPclient(FTPClient):
    def __init__(self, passive):
        FTPClientBasic.__init__(self)
        self.passive = passive


class FTPclient(object):
    """FTPclient object"""
    # Define some callbacks
    def __init__(self, job, service, params, failfunc):
        self.job = job
        self.job_id = self.job.get_job_id()
        self.ip_addr = self.job.get_ip()
        self.service = service
        self.port = self.service.get_port()
        self.proto = self.service.get_proto()
        self.params = params
        self.creator = None
        self.file_list = None
        self.debug = self.params.get_debug()
        self.failfunc = failfunc
        self.ftp_deferred = None

    @staticmethod
    def success(response):
        sys.stderr.write("Success!  Got response:\n----\n")
        if response is None:
            sys.stderr.write(None)
        else:
            sys.stderr.write(string.join(response, '\n'))
        sys.stderr.write("---\n")

    def fail(self, error):
        if isinstance(error, Failure):
            msg = error.getErrorMessage()
            self.failfunc(msg, self.service, self.job_id)
            sys.stderr.write("Job ID %s:  FTP check failed, error %s\n" % (self.job_id, msg))
        else:
            self.failfunc(error, self.service, self.job_id)
            sys.stderr.write("Job ID %s:  FTP check failed, error %s\n" % (self.job_id, error))

    @staticmethod
    def show_files(result, fileListProtocol):
        sys.stderr.write('Processed file listing:')
        for filename in fileListProtocol.files:
            sys.stderr.write('    %s: %d bytes, %s' % \
                (filename['filename'], filename['size'], filename['date']))
        sys.stderr.write('Total: %d files' % (len(fileListProtocol.files)))

    @staticmethod
    def show_buffer(result, buffer_protocol):
        sys.stderr.write("Got data: %s\n" % buffer_protocol.buffer.getvalue())

    def checkBuffer(self, result, buffer_protocol):
        found_data = buffer_protocol.buffer.getvalue()
        print "Got:"
        print result
        sys.stderr.write("Also got: |%s|\n" % found_data.strip("\r\n"))
        for content in self.service.get_contents():
            sys.stderr.write("Checking against: |%s|\n" % content.get_data())
            if found_data.strip("\r\n") == content.get_data():
                sys.stderr.write("Job ID %s: content check passed %s\n" % \
                    (self.job.get_job_id(), found_data))
                content.success()
            else:
                content.fail(found_data)
                sys.stderr.write("Job ID %s: content check failed %s\n" % \
                    (self.job.get_job_id(), found_data))

    def connectionMade(self, ftpclient):
        sys.stderr.write("Job ID: %s service %s/%s connected\n" % \
                         (self.job_id, self.service.get_port(), self.service.get_proto()))
        self.service.pass_conn()
        username = self.service.get_username()
        password = self.service.get_password()
        if username and password:
            self.login(ftpclient, self.service.get_username(), self.service.get_password())

    def run(self):
        # Get config
        passive = self.service.get_passive()
        # Create the client
        sys.stderr.write("Job ID %s:  Connecting to %s %s/%s\n" % \
                         (self.job_id, self.ip_addr, self.port, self.proto))
        self.creator = ClientCreator(reactor, CTFFTPclient, passive=passive)
        self.ftp_deferred = self.creator.connectTCP(self.ip_addr, self.port)
        self.ftp_deferred.addCallback(self.connectionMade)
        self.ftp_deferred.addErrback(self.fail)

    def procpass(self, result, ftpclient, password):
        sys.stderr.write("Got %s\n" % result)
        sys.stderr.write("Sending PASS %s\n" % password)
        d = ftpclient.queueStringCommand("PASS %s" % password)
        d.addCallback(self.check_content, ftpclient)
        d.addErrback(self.fail)

    def login(self, ftpclient, username, password):
        sys.stderr.write("Sending USER %s\n" % username)
        d = ftpclient.queueStringCommand("USER %s" % username)
        d.addCallback(self.procpass, ftpclient, password)
        d.addErrback(self.fail)

    def check_content(self, result, ftpclient):
        print result
        proto = BufferingProtocol()
        # Get the current working directory
        ftpclient.pwd().addCallbacks(self.success, self.fail)
        d = ftpclient.retrieveFile("scoring_file.txt", proto)
        d.addCallbacks(self.checkBuffer, self.fail, callbackArgs=(proto,))

