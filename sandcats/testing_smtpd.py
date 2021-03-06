# based heavily on
# https://twistedmatrix.com/documents/current/_downloads/emailserver.tac
# , which is MIT-licensed.

import sys

from zope.interface import implements

from twisted.internet import defer, reactor
from twisted.mail import smtp
from twisted.mail.imap4 import LOGINCredentials, PLAINCredentials

from twisted.cred.checkers import InMemoryUsernamePasswordDatabaseDontUse
from twisted.cred.portal import IRealm
from twisted.cred.portal import Portal


class ConsoleMessageDelivery:
    implements(smtp.IMessageDelivery)

    # receivedHeader is required; it adds a header
    def receivedHeader(self, helo, origin, recipients):
        return "Received: ConsoleMessageDelivery"

    # validateFrom is required.
    def validateFrom(self, helo, origin):
        # All addresses are accepted
        return origin

    def validateTo(self, user):
        # Only messages directed to the "console" user are accepted.
        if (user.dest.local == "benb" and
            user.dest.domain == 'benb.org'):
            return lambda: ConsoleMessage()
        raise smtp.SMTPBadRcpt(user)


class ConsoleMessage:
    implements(smtp.IMessage)

    def __init__(self):
        self.found_token = None
        self.found_recovery_success_subject = False


    def lineReceived(self, line):
        if 'Subject:'.lower() in line.lower():
            subject = line.split(':')[1].strip()
            if subject == "You successfully recovered your domain name":
                self.found_recovery_success_subject = True

        if 'X-Sandcats-recoveryToken'.lower() in line.lower():
            self.found_token = line.split(':')[1].strip()

    def eomReceived(self):
        seems_ok = (self.found_recovery_success_subject or self.found_token)
        assert seems_ok

        if self.found_token:
            print "Found recoveryToken: %s" % (self.found_token,)
        reactor.callLater(0, reactor.stop)
        return defer.succeed(None)

    def connectionLost(self):
        pass


class ConsoleSMTPFactory(smtp.SMTPFactory):
    protocol = smtp.ESMTP

    def __init__(self, *a, **kw):
        smtp.SMTPFactory.__init__(self, *a, **kw)
        self.delivery = ConsoleMessageDelivery()


    def buildProtocol(self, addr):
        p = smtp.SMTPFactory.buildProtocol(self, addr)
        p.delivery = self.delivery
        p.challengers = {"LOGIN": LOGINCredentials, "PLAIN": PLAINCredentials}
        return p



class SimpleRealm:
    implements(IRealm)

    def requestAvatar(self, avatarId, mind, *interfaces):
        if smtp.IMessageDelivery in interfaces:
            return smtp.IMessageDelivery, ConsoleMessageDelivery(), lambda: None
        raise NotImplementedError()



def main():
    from twisted.application import internet
    from twisted.application import service

    portal = Portal(SimpleRealm())
    checker = InMemoryUsernamePasswordDatabaseDontUse()
    checker.addUser("guest", "password")
    portal.registerChecker(checker)

    a = service.Application("Console SMTP Server")
    internet.TCPServer(2500, ConsoleSMTPFactory(portal)).setServiceParent(a)

    # Tell the reactor to just totally stop in a few seconds.
    WAIT_TIME=10
    reactor.callLater(WAIT_TIME, reactor.stop)

    # OK, configure is complete.
    return a

application = main()
