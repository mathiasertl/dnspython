# Copyright (C) Dnspython Contributors, see LICENSE for text of ISC license

# Copyright (C) 2001-2007, 2009-2011 Nominum, Inc.
#
# Permission to use, copy, modify, and distribute this software and its
# documentation for any purpose with or without fee is hereby granted,
# provided that the above copyright notice and this permission notice
# appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND NOMINUM DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL NOMINUM BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT
# OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

"""DNS TSIG support."""

import base64
import hashlib
import hmac
import struct

import dns.exception
import dns.rdataclass
import dns.name

class BadTime(dns.exception.DNSException):

    """The current time is not within the TSIG's validity time."""


class BadSignature(dns.exception.DNSException):

    """The TSIG signature fails to verify."""


class BadKey(dns.exception.DNSException):

    """The TSIG record owner name does not match the key."""


class BadAlgorithm(dns.exception.DNSException):

    """The TSIG algorithm does not match the key."""


class PeerError(dns.exception.DNSException):

    """Base class for all TSIG errors generated by the remote peer"""


class PeerBadKey(PeerError):

    """The peer didn't know the key we used"""


class PeerBadSignature(PeerError):

    """The peer didn't like the signature we sent"""


class PeerBadTime(PeerError):

    """The peer didn't like the time we sent"""


class PeerBadTruncation(PeerError):

    """The peer didn't like amount of truncation in the TSIG we sent"""

# TSIG Algorithms

HMAC_MD5 = dns.name.from_text("HMAC-MD5.SIG-ALG.REG.INT")
HMAC_SHA1 = dns.name.from_text("hmac-sha1")
HMAC_SHA224 = dns.name.from_text("hmac-sha224")
HMAC_SHA256 = dns.name.from_text("hmac-sha256")
HMAC_SHA384 = dns.name.from_text("hmac-sha384")
HMAC_SHA512 = dns.name.from_text("hmac-sha512")

_hashes = {
    HMAC_SHA224: hashlib.sha224,
    HMAC_SHA256: hashlib.sha256,
    HMAC_SHA384: hashlib.sha384,
    HMAC_SHA512: hashlib.sha512,
    HMAC_SHA1: hashlib.sha1,
    HMAC_MD5: hashlib.md5,
}

default_algorithm = HMAC_SHA256

BADSIG = 16
BADKEY = 17
BADTIME = 18
BADTRUNC = 22


def sign(wire, key, rdata, time=None, request_mac=None, ctx=None, multi=False):
    """Return a (tsig_rdata, mac, ctx) tuple containing the HMAC TSIG rdata
    for the input parameters, the HMAC MAC calculated by applying the
    TSIG signature algorithm, and the TSIG digest context.
    @rtype: (string, hmac.HMAC object)
    @raises ValueError: I{other_data} is too long
    @raises NotImplementedError: I{algorithm} is not supported
    """

    first = not (ctx and multi)
    (algorithm_name, digestmod) = get_algorithm(key.algorithm)
    if first:
        ctx = hmac.new(key.secret, digestmod=digestmod)
        if request_mac:
            ctx.update(struct.pack('!H', len(request_mac)))
            ctx.update(request_mac)
    ctx.update(struct.pack('!H', rdata.original_id))
    ctx.update(wire[2:])
    if first:
        ctx.update(key.name.to_digestable())
        ctx.update(struct.pack('!H', dns.rdataclass.ANY))
        ctx.update(struct.pack('!I', 0))
    if time is None:
        time = rdata.time_signed
    upper_time = (time >> 32) & 0xffff
    lower_time = time & 0xffffffff
    time_encoded = struct.pack('!HIH', upper_time, lower_time, rdata.fudge)
    other_len = len(rdata.other)
    if other_len > 65535:
        raise ValueError('TSIG Other Data is > 65535 bytes')
    if first:
        ctx.update(algorithm_name + time_encoded)
        ctx.update(struct.pack('!HH', rdata.error, other_len) + rdata.other)
    else:
        ctx.update(time_encoded)
    mac = ctx.digest()
    if multi:
        ctx = hmac.new(key.secret, digestmod=digestmod)
        ctx.update(struct.pack('!H', len(mac)))
        ctx.update(mac)
    else:
        ctx = None
    tsig = dns.rdtypes.ANY.TSIG.TSIG(dns.rdataclass.ANY, dns.rdatatype.TSIG,
                                     key.algorithm, time, rdata.fudge, mac,
                                     rdata.original_id, rdata.error,
                                     rdata.other)

    return (tsig, ctx)


def validate(wire, key, owner, rdata, now, request_mac, tsig_start, ctx=None,
             multi=False):
    """Validate the specified TSIG rdata against the other input parameters.

    @raises FormError: The TSIG is badly formed.
    @raises BadTime: There is too much time skew between the client and the
    server.
    @raises BadSignature: The TSIG signature did not validate
    @rtype: hmac.HMAC object"""

    (adcount,) = struct.unpack("!H", wire[10:12])
    if adcount == 0:
        raise dns.exception.FormError
    adcount -= 1
    new_wire = wire[0:10] + struct.pack("!H", adcount) + wire[12:tsig_start]
    if rdata.error != 0:
        if rdata.error == BADSIG:
            raise PeerBadSignature
        elif rdata.error == BADKEY:
            raise PeerBadKey
        elif rdata.error == BADTIME:
            raise PeerBadTime
        elif rdata.error == BADTRUNC:
            raise PeerBadTruncation
        else:
            raise PeerError('unknown TSIG error code %d' % rdata.error)
    if abs(rdata.time_signed - now) > rdata.fudge:
        raise BadTime
    if key.name != owner:
        raise BadKey
    if key.algorithm != rdata.algorithm:
        raise BadAlgorithm
    (our_rdata, ctx) = sign(new_wire, key, rdata, None, request_mac, ctx, multi)
    if our_rdata.mac != rdata.mac:
        raise BadSignature
    return ctx


def get_algorithm(algorithm):
    """Returns the wire format string and the hash module to use for the
    specified TSIG algorithm

    @rtype: (string, hash constructor)
    @raises NotImplementedError: I{algorithm} is not supported
    """

    if isinstance(algorithm, str):
        algorithm = dns.name.from_text(algorithm)

    try:
        return (algorithm.to_digestable(), _hashes[algorithm])
    except KeyError:
        raise NotImplementedError("TSIG algorithm " + str(algorithm) +
                                  " is not supported")

class Key:
    def __init__(self, name, secret, algorithm=default_algorithm):
        if isinstance(name, str):
            name = dns.name.from_text(name)
        self.name = name
        if isinstance(secret, str):
            secret = base64.decodebytes(secret.encode())
        self.secret = secret
        self.algorithm = algorithm

    def __eq__(self, other):
        return (isinstance(other, Key) and
                self.name == other.name and
                self.secret == other.secret and
                self.algorithm == other.algorithm)
