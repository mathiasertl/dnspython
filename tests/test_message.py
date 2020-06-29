# -*- coding: utf-8
# Copyright (C) Dnspython Contributors, see LICENSE for text of ISC license

# Copyright (C) 2003-2007, 2009-2011 Nominum, Inc.
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

import os
import unittest
import binascii

import dns.exception
import dns.flags
import dns.message
import dns.name
import dns.rdataclass
import dns.rdatatype
import dns.rrset
import dns.update

def here(filename):
    return os.path.join(os.path.dirname(__file__), filename)

query_text = """id 1234
opcode QUERY
rcode NOERROR
flags RD
edns 0
eflags DO
payload 4096
;QUESTION
wwww.dnspython.org. IN A
;ANSWER
;AUTHORITY
;ADDITIONAL"""

goodhex = b'04d201000001000000000001047777777709646e73707974686f6e' \
          b'036f726700000100010000291000000080000000'

goodwire = binascii.unhexlify(goodhex)

answer_text = """id 1234
opcode QUERY
rcode NOERROR
flags QR AA RD
;QUESTION
dnspython.org. IN SOA
;ANSWER
dnspython.org. 3600 IN SOA woof.dnspython.org. hostmaster.dnspython.org. 2003052700 3600 1800 604800 3600
;AUTHORITY
dnspython.org. 3600 IN NS ns1.staff.nominum.org.
dnspython.org. 3600 IN NS ns2.staff.nominum.org.
dnspython.org. 3600 IN NS woof.play-bow.org.
;ADDITIONAL
woof.play-bow.org. 3600 IN A 204.152.186.150
"""

goodhex2 = '04d2 8500 0001 0001 0003 0001' \
           '09646e73707974686f6e036f726700 0006 0001' \
           'c00c 0006 0001 00000e10 0028 ' \
               '04776f6f66c00c 0a686f73746d6173746572c00c' \
               '7764289c 00000e10 00000708 00093a80 00000e10' \
           'c00c 0002 0001 00000e10 0014' \
               '036e7331057374616666076e6f6d696e756dc016' \
           'c00c 0002 0001 00000e10 0006 036e7332c063' \
           'c00c 0002 0001 00000e10 0010 04776f6f6608706c61792d626f77c016' \
           'c091 0001 0001 00000e10 0004 cc98ba96'


goodwire2 = binascii.unhexlify(goodhex2.replace(' ', '').encode())

query_text_2 = """id 1234
opcode QUERY
rcode 4095
flags RD
edns 0
eflags DO
payload 4096
;QUESTION
wwww.dnspython.org. IN A
;ANSWER
;AUTHORITY
;ADDITIONAL"""

goodhex3 = b'04d2010f0001000000000001047777777709646e73707974686f6e' \
           b'036f726700000100010000291000ff0080000000'

goodwire3 = binascii.unhexlify(goodhex3)

idna_text = """id 1234
opcode QUERY
rcode NOERROR
flags QR AA RD
;QUESTION
Königsgäßchen. IN NS
;ANSWER
Königsgäßchen. 3600 IN NS Königsgäßchen.
"""

class MessageTestCase(unittest.TestCase):

    def test_class(self):
        m = dns.message.from_text(query_text)
        self.assertTrue(isinstance(m, dns.message.QueryMessage))

    def test_comparison_eq1(self):
        q1 = dns.message.from_text(query_text)
        q2 = dns.message.from_text(query_text)
        self.assertEqual(q1, q2)

    def test_comparison_ne1(self):
        q1 = dns.message.from_text(query_text)
        q2 = dns.message.from_text(query_text)
        q2.id = 10
        self.assertNotEqual(q1, q2)

    def test_comparison_ne2(self):
        q1 = dns.message.from_text(query_text)
        q2 = dns.message.from_text(query_text)
        q2.question = []
        self.assertNotEqual(q1, q2)

    def test_comparison_ne3(self):
        q1 = dns.message.from_text(query_text)
        self.assertNotEqual(q1, 1)

    def test_EDNS_to_wire1(self):
        q = dns.message.from_text(query_text)
        w = q.to_wire()
        self.assertEqual(w, goodwire)

    def test_EDNS_from_wire1(self):
        m = dns.message.from_wire(goodwire)
        self.assertEqual(str(m), query_text)

    def test_EDNS_to_wire2(self):
        q = dns.message.from_text(query_text_2)
        w = q.to_wire()
        self.assertEqual(w, goodwire3)

    def test_EDNS_from_wire2(self):
        m = dns.message.from_wire(goodwire3)
        self.assertEqual(str(m), query_text_2)

    def test_EDNS_options_wire(self):
        m = dns.message.make_query('foo', 'A')
        opt = dns.edns.GenericOption(3, b'data')
        m.use_edns(options=[opt])
        m2 = dns.message.from_wire(m.to_wire())
        self.assertEqual(m2.edns, 0)
        self.assertEqual(len(m2.options), 1)
        self.assertEqual(m2.options[0], opt)

    def test_TooBig(self):
        def bad():
            q = dns.message.from_text(query_text)
            for i in range(0, 25):
                rrset = dns.rrset.from_text('foo%d.' % i, 3600,
                                            dns.rdataclass.IN,
                                            dns.rdatatype.A,
                                            '10.0.0.%d' % i)
                q.additional.append(rrset)
            q.to_wire(max_size=512)
        self.assertRaises(dns.exception.TooBig, bad)

    def test_answer1(self):
        a = dns.message.from_text(answer_text)
        wire = a.to_wire(want_shuffle=False)
        self.assertEqual(wire, goodwire2)

    def test_TrailingJunk(self):
        def bad():
            badwire = goodwire + b'\x00'
            dns.message.from_wire(badwire)
        self.assertRaises(dns.message.TrailingJunk, bad)

    def test_ShortHeader(self):
        def bad():
            badwire = b'\x00' * 11
            dns.message.from_wire(badwire)
        self.assertRaises(dns.message.ShortHeader, bad)

    def test_RespondingToResponse(self):
        def bad():
            q = dns.message.make_query('foo', 'A')
            r1 = dns.message.make_response(q)
            dns.message.make_response(r1)
        self.assertRaises(dns.exception.FormError, bad)

    def test_RespondingToEDNSRequestAndSettingRA(self):
        q = dns.message.make_query('foo', 'A', use_edns=0)
        r = dns.message.make_response(q, True)
        self.assertTrue(r.flags & dns.flags.RA != 0)
        self.assertEqual(r.edns, 0)

    def test_ExtendedRcodeSetting(self):
        m = dns.message.make_query('foo', 'A')
        m.set_rcode(4095)
        self.assertEqual(m.rcode(), 4095)
        self.assertEqual(m.edns, 0)
        m.set_rcode(2)
        self.assertEqual(m.rcode(), 2)

    def test_EDNSVersionCoherence(self):
        m = dns.message.make_query('foo', 'A')
        m.use_edns(1)
        self.assertEqual((m.ednsflags >> 16) & 0xFF, 1)

    def test_SettingNoEDNSOptionsImpliesNoEDNS(self):
        m = dns.message.make_query('foo', 'A')
        self.assertEqual(m.edns, -1)

    def test_SettingEDNSFlagsImpliesEDNS(self):
        m = dns.message.make_query('foo', 'A', ednsflags=dns.flags.DO)
        self.assertEqual(m.edns, 0)

    def test_SettingEDNSPayloadImpliesEDNS(self):
        m = dns.message.make_query('foo', 'A', payload=4096)
        self.assertEqual(m.edns, 0)

    def test_SettingEDNSRequestPayloadImpliesEDNS(self):
        m = dns.message.make_query('foo', 'A', request_payload=4096)
        self.assertEqual(m.edns, 0)

    def test_SettingOptionsImpliesEDNS(self):
        m = dns.message.make_query('foo', 'A', options=[])
        self.assertEqual(m.edns, 0)

    def test_FindRRset(self):
        a = dns.message.from_text(answer_text)
        n = dns.name.from_text('dnspython.org.')
        rrs1 = a.find_rrset(a.answer, n, dns.rdataclass.IN, dns.rdatatype.SOA)
        rrs2 = a.find_rrset(dns.message.ANSWER, n, dns.rdataclass.IN,
                            dns.rdatatype.SOA)
        self.assertEqual(rrs1, rrs2)

    def test_FindRRsetUnindexed(self):
        a = dns.message.from_text(answer_text)
        a.index = None
        n = dns.name.from_text('dnspython.org.')
        rrs1 = a.find_rrset(a.answer, n, dns.rdataclass.IN, dns.rdatatype.SOA)
        rrs2 = a.find_rrset(dns.message.ANSWER, n, dns.rdataclass.IN,
                            dns.rdatatype.SOA)
        self.assertEqual(rrs1, rrs2)

    def test_GetRRset(self):
        a = dns.message.from_text(answer_text)
        a.index = None
        n = dns.name.from_text('dnspython.org.')
        rrs1 = a.get_rrset(a.answer, n, dns.rdataclass.IN, dns.rdatatype.SOA)
        rrs2 = a.get_rrset(dns.message.ANSWER, n, dns.rdataclass.IN,
                           dns.rdatatype.SOA)
        self.assertEqual(rrs1, rrs2)

    def test_GetNonexistentRRset(self):
        a = dns.message.from_text(answer_text)
        a.index = None
        n = dns.name.from_text('dnspython.org.')
        rrs1 = a.get_rrset(a.answer, n, dns.rdataclass.IN, dns.rdatatype.TXT)
        rrs2 = a.get_rrset(dns.message.ANSWER, n, dns.rdataclass.IN,
                           dns.rdatatype.TXT)
        self.assertTrue(rrs1 is None)
        self.assertEqual(rrs1, rrs2)

    def test_CleanTruncated(self):
        def bad():
            a = dns.message.from_text(answer_text)
            a.flags |= dns.flags.TC
            wire = a.to_wire(want_shuffle=False)
            dns.message.from_wire(wire, raise_on_truncation=True)
        self.assertRaises(dns.message.Truncated, bad)

    def test_MessyTruncated(self):
        def bad():
            a = dns.message.from_text(answer_text)
            a.flags |= dns.flags.TC
            wire = a.to_wire(want_shuffle=False)
            dns.message.from_wire(wire[:-3], raise_on_truncation=True)
        self.assertRaises(dns.message.Truncated, bad)

    def test_IDNA_2003(self):
        a = dns.message.from_text(idna_text, idna_codec=dns.name.IDNA_2003)
        rrs = dns.rrset.from_text_list('xn--knigsgsschen-lcb0w.', 30,
                                       'in', 'ns',
                                       ['xn--knigsgsschen-lcb0w.'],
                                       idna_codec=dns.name.IDNA_2003)
        self.assertEqual(a.answer[0], rrs)

    @unittest.skipUnless(dns.name.have_idna_2008,
                         'Python idna cannot be imported; no IDNA2008')
    def test_IDNA_2008(self):
        a = dns.message.from_text(idna_text, idna_codec=dns.name.IDNA_2008)
        rrs = dns.rrset.from_text_list('xn--knigsgchen-b4a3dun.', 30,
                                       'in', 'ns',
                                       ['xn--knigsgchen-b4a3dun.'],
                                       idna_codec=dns.name.IDNA_2008)
        self.assertEqual(a.answer[0], rrs)

    def test_bad_section_number(self):
        m = dns.message.make_query('foo', 'A')
        self.assertRaises(ValueError,
                          lambda: m.section_number(123))

    def test_section_from_number(self):
        m = dns.message.make_query('foo', 'A')
        self.assertEqual(m.section_from_number(dns.message.QUESTION),
                         m.question)
        self.assertEqual(m.section_from_number(dns.message.ANSWER),
                         m.answer)
        self.assertEqual(m.section_from_number(dns.message.AUTHORITY),
                         m.authority)
        self.assertEqual(m.section_from_number(dns.message.ADDITIONAL),
                         m.additional)
        self.assertRaises(ValueError,
                          lambda: m.section_from_number(999))

    def test_wanting_EDNS_true_is_EDNS0(self):
        m = dns.message.make_query('foo', 'A')
        self.assertEqual(m.edns, -1)
        m.use_edns(True)
        self.assertEqual(m.edns, 0)

    def test_wanting_DNSSEC_turns_on_EDNS(self):
        m = dns.message.make_query('foo', 'A')
        self.assertEqual(m.edns, -1)
        m.want_dnssec()
        self.assertEqual(m.edns, 0)

    def test_from_file(self):
        m = dns.message.from_file(here('query'))
        expected = dns.message.from_text(query_text)
        self.assertEqual(m, expected)

    def test_explicit_header_comment(self):
        m = dns.message.from_text(';HEADER\n' + query_text)
        expected = dns.message.from_text(query_text)
        self.assertEqual(m, expected)

    def test_repr(self):
        q = dns.message.from_text(query_text)
        self.assertEqual(repr(q), '<DNS message, ID 1234>')

    def test_non_question_setters(self):
        rrset = dns.rrset.from_text('foo', 300, 'in', 'a', '10.0.0.1')
        q = dns.message.QueryMessage(id=1)
        q.answer = [rrset]
        self.assertEqual(q.sections[1], [rrset])
        self.assertEqual(q.sections[2], [])
        self.assertEqual(q.sections[3], [])
        q.authority = [rrset]
        self.assertEqual(q.sections[2], [rrset])
        self.assertEqual(q.sections[3], [])
        q.additional = [rrset]
        self.assertEqual(q.sections[3], [rrset])

    def test_not_a_response(self):
        q = dns.message.QueryMessage(id=1)
        self.assertFalse(q.is_response(q))
        r = dns.message.QueryMessage(id=2)
        r.flags = dns.flags.QR
        self.assertFalse(q.is_response(r))
        r = dns.update.UpdateMessage(id=1)
        self.assertFalse(q.is_response(r))
        q1 = dns.message.make_query('www.dnspython.org.', 'a')
        q2 = dns.message.make_query('www.google.com.', 'a')
        # Give them the same id, as we want to test if responses for
        # differing questions are rejected.
        q1.id = 1
        q2.id = 1
        r = dns.message.make_response(q2)
        self.assertFalse(q1.is_response(r))
        # Test the other case of differing questions, where there is
        # something in the response's question section that is not in
        # the question's.  We have to do multiple questions to test
        # this :)
        r = dns.message.make_query('www.dnspython.org.', 'a')
        r.flags |= dns.flags.QR
        r.id = 1
        r.find_rrset(r.question, dns.name.from_text('example'),
                     dns.rdataclass.IN, dns.rdatatype.A, create=True,
                     force_unique=True)
        self.assertFalse(q1.is_response(r))

    def test_more_not_equal_cases(self):
        q1 = dns.message.make_query('www.dnspython.org.', 'a')
        q2 = dns.message.make_query('www.dnspython.org.', 'a')
        # ensure ids are same
        q1.id = 1
        q2.id = 1
        # and flags are different
        q2.flags |= dns.flags.QR
        self.assertFalse(q1 == q2)
        q2.flags = q1.flags
        q2.find_rrset(q2.question, dns.name.from_text('example'),
                      dns.rdataclass.IN, dns.rdatatype.A, create=True,
                      force_unique=True)
        self.assertFalse(q1 == q2)

    def test_edns_properties(self):
        q = dns.message.make_query('www.dnspython.org.', 'a')
        self.assertEqual(q.edns, -1)
        self.assertEqual(q.payload, 0)
        self.assertEqual(q.options, ())
        q = dns.message.make_query('www.dnspython.org.', 'a', use_edns=0,
                                   payload=4096)
        self.assertEqual(q.edns, 0)
        self.assertEqual(q.payload, 4096)
        self.assertEqual(q.options, ())

    def test_generic_message_class(self):
        q1 = dns.message.Message(id=1)
        q1.set_opcode(dns.opcode.NOTIFY)
        q1.flags |= dns.flags.AA
        q1.find_rrset(q1.question, dns.name.from_text('example'),
                      dns.rdataclass.IN, dns.rdatatype.SOA, create=True,
                      force_unique=True)
        w = q1.to_wire()
        q2 = dns.message.from_wire(w)
        self.assertTrue(isinstance(q2, dns.message.Message))
        self.assertFalse(isinstance(q2, dns.message.QueryMessage))
        self.assertFalse(isinstance(q2, dns.update.UpdateMessage))
        self.assertEqual(q1, q2)

if __name__ == '__main__':
    unittest.main()
