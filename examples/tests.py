# -*- coding: utf-8 -*-
#
# django-ldapdb
# Copyright (c) 2009-2011, Bolloré telecom
# Copyright (c) 2013, Jeremy Lainé
# All rights reserved.
#
# See AUTHORS file for a full list of contributors.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#     1. Redistributions of source code must retain the above copyright notice,
#        this list of conditions and the following disclaimer.
#
#     2. Redistributions in binary form must reproduce the above copyright
#        notice, this list of conditions and the following disclaimer in the
#        documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#

from __future__ import unicode_literals

import datetime

import ldap
import volatildap

from django.conf import settings
from django.db.models import Q, Count
from django.test import TestCase

from ldapdb.backends.ldap.compiler import query_as_ldap
from examples.models import LdapUser, LdapGroup


#admin = ('cn=admin,dc=example,dc=org', {'userPassword': ['test']})
groups = ('ou=groups,dc=example,dc=org', {
    'objectClass': ['top', 'organizationalUnit'], 'ou': ['groups']})
people = ('ou=people,dc=example,dc=org', {
    'objectClass': ['top', 'organizationalUnit'], 'ou': ['groups']})
contacts = ('ou=contacts,ou=groups,dc=example,dc=org', {
    'objectClass': ['top', 'organizationalUnit'], 'ou': ['groups']})
foogroup = ('cn=foogroup,ou=groups,dc=example,dc=org', {
    'objectClass': ['posixGroup'], 'memberUid': ['foouser', 'baruser'],
    'gidNumber': ['1000'], 'cn': ['foogroup']})
bargroup = ('cn=bargroup,ou=groups,dc=example,dc=org', {
    'objectClass': ['posixGroup'], 'memberUid': ['zoouser', 'baruser'],
    'gidNumber': ['1001'], 'cn': ['bargroup']})
wizgroup = ('cn=wizgroup,ou=groups,dc=example,dc=org', {
    'objectClass': ['posixGroup'], 'memberUid': ['wizuser', 'baruser'],
    'gidNumber': ['1002'], 'cn': ['wizgroup']})
foouser = ('uid=foouser,ou=people,dc=example,dc=org', {
    'cn': [b'F\xc3\xb4o Us\xc3\xa9r'],
    'objectClass': ['posixAccount', 'shadowAccount', 'inetOrgPerson'],
    'loginShell': ['/bin/bash'],
    'jpegPhoto': [
        b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff'
        b'\xfe\x00\x1cCreated with GIMP on a Mac\xff\xdb\x00C\x00\x05\x03\x04'
        b'\x04\x04\x03\x05\x04\x04\x04\x05\x05\x05\x06\x07\x0c\x08\x07\x07\x07'
        b'\x07\x0f\x0b\x0b\t\x0c\x11\x0f\x12\x12\x11\x0f\x11\x11\x13\x16\x1c'
        b'\x17\x13\x14\x1a\x15\x11\x11\x18!\x18\x1a\x1d\x1d\x1f\x1f\x1f\x13'
        b'\x17"$"\x1e$\x1c\x1e\x1f\x1e\xff\xdb\x00C\x01\x05\x05\x05\x07\x06\x07'
        b'\x0e\x08\x08\x0e\x1e\x14\x11\x14\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e'
        b'\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e'
        b'\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e'
        b'\x1e\x1e\x1e\x1e\x1e\x1e\x1e\xff\xc0\x00\x11\x08\x00\x08\x00\x08\x03'
        b'\x01"\x00\x02\x11\x01\x03\x11\x01\xff\xc4\x00\x15\x00\x01\x01\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x08\xff\xc4\x00'
        b'\x19\x10\x00\x03\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        b'\x00\x00\x01\x02\x06\x11A\xff\xc4\x00\x14\x01\x01\x00\x00\x00\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xc4\x00\x14\x11\x01'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff'
        b'\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00?\x00\x9d\xf29wU5Q\xd6'
        b'\xfd\x00\x01\xff\xd9'],
    'uidNumber': ['2000'], 'gidNumber': ['1000'], 'sn': [b'Us\xc3\xa9r'],
    'homeDirectory': ['/home/foouser'], 'givenName': [b'F\xc3\xb4o'],
    'uid': ['foouser']})


class BaseTestCase(TestCase):
    directory = {}

    @classmethod
    def setUpClass(cls):
        super(BaseTestCase, cls).setUpClass()
        cls.ldap_server = volatildap.LdapServer(
            initial_data=cls.directory,
            schemas=['core.schema', 'cosine.schema', 'inetorgperson.schema', 'nis.schema'],
        )
        settings.DATABASES['ldap']['USER'] = cls.ldap_server.rootdn
        settings.DATABASES['ldap']['PASSWORD'] = cls.ldap_server.rootpw
        settings.DATABASES['ldap']['NAME'] = cls.ldap_server.uri

    @classmethod
    def tearDownClass(cls):
        cls.ldap_server.stop()
        super(BaseTestCase, cls).tearDownClass()

    def setUp(self):
        super(BaseTestCase, self).setUp()
        self.ldap_server.start()


class ConnectionTestCase(BaseTestCase):
    directory = dict([people, foouser])

    def test_connection_options(self):
        LdapUser.objects.get(username='foouser')
        self.assertEqual(self.ldapobj.get_option(ldap.OPT_X_TLS_DEMAND), True)

    def test_start_tls(self):
        #self.assertFalse(self.ldapobj.tls_enabled)
        LdapUser.objects.get(username='foouser')

    def test_bound_as_admin(self):
        LdapUser.objects.get(username='foouser')
        #self.assertEqual(self.ldapobj.bound_as, admin[0])


class GroupTestCase(BaseTestCase):
    directory = dict([groups, foogroup, bargroup, wizgroup, people, foouser])

    def test_count_none(self):
        qs = LdapGroup.objects.none()
        self.assertEqual(qs.count(), 0)

    def test_count_all(self):
        qs = LdapGroup.objects.all()
        self.assertEqual(qs.count(), 3)

    def test_aggregate_count(self):
        qs = LdapGroup.objects.all()
        result = qs.aggregate(num_groups=Count('name'))
        self.assertEquals(result['num_groups'], 3)

    def test_annotate_count(self):
        groups = LdapGroup.objects.order_by('name').annotate(num_usernames=Count('usernames'))
        self.assertEquals(len(groups), 3)
        self.assertEquals(groups[0].name, 'bargroup')
        self.assertEquals(groups[0].num_usernames, 2)
        self.assertEquals(groups[1].name, 'foogroup')
        self.assertEquals(groups[1].num_usernames, 2)
        self.assertEquals(groups[2].name, 'wizgroup')
        self.assertEquals(groups[2].num_usernames, 2)
        groups = LdapGroup.objects.filter(name='foogroup').annotate(num_usernames=Count('usernames'))
        self.assertEquals(len(groups), 1)
        self.assertEquals(groups[0].name, 'foogroup')
        self.assertEquals(groups[0].num_usernames, 2)
        groups = LdapGroup.objects.annotate(num_usernames=Count('usernames')).filter(name='foogroup')
        self.assertEquals(len(groups), 1)
        self.assertEquals(groups[0].name, 'foogroup')
        self.assertEquals(groups[0].num_usernames, 2)

    def test_length_all(self):
        qs = LdapGroup.objects.all()
        self.assertEquals(len(qs), 3)

    def test_length_none(self):
        qs = LdapGroup.objects.none()
        self.assertEquals(len(qs), 0)
        self.assertEquals(self.ldapobj.methods_called(), [])

    def test_ldap_filter(self):
        # single filter
        qs = LdapGroup.objects.filter(name='foogroup')
        self.assertEquals(query_as_ldap(qs.query),
                          '(&(objectClass=posixGroup)(cn=foogroup))')

        qs = LdapGroup.objects.filter(Q(name='foogroup'))
        self.assertEquals(query_as_ldap(qs.query),
                          '(&(objectClass=posixGroup)(cn=foogroup))')

        # AND filter
        qs = LdapGroup.objects.filter(gid=1000, name='foogroup')
        self.assertEquals(query_as_ldap(qs.query),
                          '(&(objectClass=posixGroup)(&(cn=foogroup)'
                          '(gidNumber=1000)))')

        qs = LdapGroup.objects.filter(Q(gid=1000) & Q(name='foogroup'))
        self.assertEquals(query_as_ldap(qs.query),
                          '(&(objectClass=posixGroup)(&(cn=foogroup)'
                          '(gidNumber=1000)))')

        # OR filter
        qs = LdapGroup.objects.filter(Q(gid=1000) | Q(name='foogroup'))
        self.assertEquals(query_as_ldap(qs.query),
                          '(&(objectClass=posixGroup)(|(cn=foogroup)'
                          '(gidNumber=1000)))')

        # single exclusion
        qs = LdapGroup.objects.exclude(name='foogroup')
        self.assertEquals(query_as_ldap(qs.query),
                          '(&(objectClass=posixGroup)(!(cn=foogroup)))')

        qs = LdapGroup.objects.filter(~Q(name='foogroup'))
        self.assertEquals(query_as_ldap(qs.query),
                          '(&(objectClass=posixGroup)(!(cn=foogroup)))')

        # multiple exclusion
        qs = LdapGroup.objects.exclude(name='foogroup', gid=1000)
        self.assertEquals(query_as_ldap(qs.query),
                          '(&(objectClass=posixGroup)(!(&(cn=foogroup)'
                          '(gidNumber=1000))))')

        qs = LdapGroup.objects.filter(name='foogroup').exclude(gid=1000)
        self.assertEquals(query_as_ldap(qs.query),
                          '(&(objectClass=posixGroup)(&(!(gidNumber=1000))(cn=foogroup)))')

    def test_filter(self):
        qs = LdapGroup.objects.filter(name='foogroup')
        self.assertEquals(qs.count(), 1)

        qs = LdapGroup.objects.filter(name='foogroup')
        self.assertEquals(len(qs), 1)

        g = qs[0]
        self.assertEquals(g.dn, 'cn=foogroup,%s' % LdapGroup.base_dn)
        self.assertEquals(g.name, 'foogroup')
        self.assertEquals(g.gid, 1000)
        self.assertEquals(g.usernames, ['foouser', 'baruser'])

        # try to filter non-existent entries
        qs = LdapGroup.objects.filter(name='does_not_exist')
        self.assertEquals(qs.count(), 0)

        qs = LdapGroup.objects.filter(name='does_not_exist')
        self.assertEquals(len(qs), 0)

    def test_get(self):
        g = LdapGroup.objects.get(name='foogroup')
        self.assertEquals(g.dn, 'cn=foogroup,%s' % LdapGroup.base_dn)
        self.assertEquals(g.name, 'foogroup')
        self.assertEquals(g.gid, 1000)
        self.assertEquals(g.usernames, ['foouser', 'baruser'])

        # try to get a non-existent entry
        self.assertRaises(LdapGroup.DoesNotExist, LdapGroup.objects.get,
                          name='does_not_exist')

    def test_insert(self):
        g = LdapGroup()
        g.name = 'newgroup'
        g.gid = 1010
        g.usernames = ['someuser', 'foouser']
        g.save()
        self.assertEquals(self.ldapobj.methods_called(), [
            'initialize',
            'simple_bind_s',
            'add_s'])

        # check group was created
        new = LdapGroup.objects.get(name='newgroup')
        self.assertEquals(new.name, 'newgroup')
        self.assertEquals(new.gid, 1010)
        self.assertEquals(new.usernames, ['someuser', 'foouser'])

    def test_order_by(self):
        # ascending name
        qs = LdapGroup.objects.order_by('name')
        self.assertEquals(len(qs), 3)
        self.assertEquals(qs[0].name, 'bargroup')
        self.assertEquals(qs[1].name, 'foogroup')
        self.assertEquals(qs[2].name, 'wizgroup')

        # descending name
        qs = LdapGroup.objects.order_by('-name')
        self.assertEquals(len(qs), 3)
        self.assertEquals(qs[0].name, 'wizgroup')
        self.assertEquals(qs[1].name, 'foogroup')
        self.assertEquals(qs[2].name, 'bargroup')

        # ascending gid
        qs = LdapGroup.objects.order_by('gid')
        self.assertEquals(len(qs), 3)
        self.assertEquals(qs[0].gid, 1000)
        self.assertEquals(qs[1].gid, 1001)
        self.assertEquals(qs[2].gid, 1002)

        # descending gid
        qs = LdapGroup.objects.order_by('-gid')
        self.assertEquals(len(qs), 3)
        self.assertEquals(qs[0].gid, 1002)
        self.assertEquals(qs[1].gid, 1001)
        self.assertEquals(qs[2].gid, 1000)

        # ascending pk
        qs = LdapGroup.objects.order_by('pk')
        self.assertEquals(len(qs), 3)
        self.assertEquals(qs[0].name, 'bargroup')
        self.assertEquals(qs[1].name, 'foogroup')
        self.assertEquals(qs[2].name, 'wizgroup')

        # descending pk
        qs = LdapGroup.objects.order_by('-pk')
        self.assertEquals(len(qs), 3)
        self.assertEquals(qs[0].name, 'wizgroup')
        self.assertEquals(qs[1].name, 'foogroup')
        self.assertEquals(qs[2].name, 'bargroup')

    def test_bulk_delete(self):
        LdapGroup.objects.all().delete()

        qs = LdapGroup.objects.all()
        self.assertEquals(len(qs), 0)

    def test_bulk_delete_none(self):
        LdapGroup.objects.none().delete()

        qs = LdapGroup.objects.all()
        self.assertEquals(len(qs), 3)

    def test_slice(self):
        qs = LdapGroup.objects.order_by('gid')
        objs = list(qs)
        self.assertEquals(len(objs), 3)
        self.assertEquals(objs[0].gid, 1000)
        self.assertEquals(objs[1].gid, 1001)
        self.assertEquals(objs[2].gid, 1002)

        # limit only
        qs = LdapGroup.objects.order_by('gid')
        objs = qs[:2]
        self.assertEquals(objs.count(), 2)

        objs = qs[:2]
        self.assertEquals(len(objs), 2)
        self.assertEquals(objs[0].gid, 1000)
        self.assertEquals(objs[1].gid, 1001)

        # offset only
        qs = LdapGroup.objects.order_by('gid')
        objs = qs[1:]
        self.assertEquals(objs.count(), 2)

        objs = qs[1:]
        self.assertEquals(len(objs), 2)
        self.assertEquals(objs[0].gid, 1001)
        self.assertEquals(objs[1].gid, 1002)

        # offset and limit
        qs = LdapGroup.objects.order_by('gid')
        objs = qs[1:2]
        self.assertEquals(objs.count(), 1)

        objs = qs[1:2]
        self.assertEquals(len(objs), 1)
        self.assertEquals(objs[0].gid, 1001)

    def test_update(self):
        g = LdapGroup.objects.get(name='foogroup')
        g.gid = 1002
        g.usernames = ['foouser2', u'barusér2']
        g.save()

        # check group was updated
        new = LdapGroup.objects.get(name='foogroup')
        self.assertEquals(new.name, 'foogroup')
        self.assertEquals(new.gid, 1002)
        self.assertEquals(new.usernames, ['foouser2', u'barusér2'])

    def test_update_change_dn(self):
        g = LdapGroup.objects.get(name='foogroup')
        g.name = 'foogroup2'
        g.save()
        self.assertEquals(g.dn, 'cn=foogroup2,%s' % LdapGroup.base_dn)

        # check group was updated
        new = LdapGroup.objects.get(name='foogroup2')
        self.assertEquals(new.name, 'foogroup2')
        self.assertEquals(new.gid, 1000)
        self.assertEquals(new.usernames, ['foouser', 'baruser'])

    def test_values(self):
        qs = sorted(LdapGroup.objects.values('name'))
        self.assertEquals(len(qs), 3)
        self.assertEquals(qs[0], {'name': 'bargroup'})
        self.assertEquals(qs[1], {'name': 'foogroup'})
        self.assertEquals(qs[2], {'name': 'wizgroup'})

    def test_values_list(self):
        qs = sorted(LdapGroup.objects.values_list('name'))
        self.assertEquals(len(qs), 3)
        self.assertEquals(qs[0], ('bargroup',))
        self.assertEquals(qs[1], ('foogroup',))
        self.assertEquals(qs[2], ('wizgroup',))

    def test_delete(self):
        g = LdapGroup.objects.get(name='foogroup')
        g.delete()

        qs = LdapGroup.objects.all()
        self.assertEquals(len(qs), 2)


class UserTestCase(TestCase):
    directory = dict([admin, groups, people, foouser])

    @classmethod
    def setUpClass(cls):
        cls.mockldap = MockLdap(cls.directory)

    @classmethod
    def tearDownClass(cls):
        del cls.mockldap

    def setUp(self):
        self.mockldap.start()
        self.ldapobj = self.mockldap[settings.DATABASES['ldap']['NAME']]

    def tearDown(self):
        self.mockldap.stop()
        del self.ldapobj

    def test_get(self):
        u = LdapUser.objects.get(username='foouser')
        self.assertEquals(u.first_name, u'Fôo')
        self.assertEquals(u.last_name, u'Usér')
        self.assertEquals(u.full_name, u'Fôo Usér')

        self.assertEquals(u.group, 1000)
        self.assertEquals(u.home_directory, '/home/foouser')
        self.assertEquals(u.uid, 2000)
        self.assertEquals(u.username, 'foouser')
        self.assertEquals(u.photo, '\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01'
                          '\x01\x00H\x00H\x00\x00\xff\xfe\x00\x1cCreated with '
                          'GIMP on a Mac\xff\xdb\x00C\x00\x05\x03\x04\x04\x04'
                          '\x03\x05\x04\x04\x04\x05\x05\x05\x06\x07\x0c\x08'
                          '\x07\x07\x07\x07\x0f\x0b\x0b\t\x0c\x11\x0f\x12\x12'
                          '\x11\x0f\x11\x11\x13\x16\x1c\x17\x13\x14\x1a\x15'
                          '\x11\x11\x18!\x18\x1a\x1d\x1d\x1f\x1f\x1f\x13\x17'
                          '"$"\x1e$\x1c\x1e\x1f\x1e\xff\xdb\x00C\x01\x05\x05'
                          '\x05\x07\x06\x07\x0e\x08\x08\x0e\x1e\x14\x11\x14'
                          '\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e'
                          '\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e'
                          '\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e'
                          '\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e'
                          '\x1e\x1e\xff\xc0\x00\x11\x08\x00\x08\x00\x08\x03'
                          '\x01"\x00\x02\x11\x01\x03\x11\x01\xff\xc4\x00\x15'
                          '\x00\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                          '\x00\x00\x00\x00\x00\x00\x08\xff\xc4\x00\x19\x10'
                          '\x00\x03\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00'
                          '\x00\x00\x00\x00\x00\x01\x02\x06\x11A\xff\xc4\x00'
                          '\x14\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                          '\x00\x00\x00\x00\x00\x00\x00\xff\xc4\x00\x14\x11'
                          '\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                          '\x00\x00\x00\x00\x00\xff\xda\x00\x0c\x03\x01\x00'
                          '\x02\x11\x03\x11\x00?\x00\x9d\xf29wU5Q\xd6\xfd\x00'
                          '\x01\xff\xd9')
        self.assertEquals(u.date_of_birth, datetime.date(1982, 6, 12))
        self.assertEquals(u.latitude, 3.14)

        self.assertRaises(LdapUser.DoesNotExist, LdapUser.objects.get,
                          username='does_not_exist')

    def test_update(self):
        u = LdapUser.objects.get(username='foouser')
        u.first_name = u'Fôo2'
        u.save()

        # make sure DN gets updated if we change the pk
        u.username = 'foouser2'
        u.save()
        self.assertEquals(u.dn, 'uid=foouser2,%s' % LdapUser.base_dn)


class ScopedTestCase(BaseTestCase):
    directory = dict([groups, people, foogroup, contacts])

    def setUp(self):
        super(ScopedTestCase, self).setUp()
        self.scoped_model = LdapGroup.scoped("ou=contacts,%s" %
                                             LdapGroup.base_dn)

    def test_scope(self):
        ScopedGroup = self.scoped_model

        qs = LdapGroup.objects.all()
        self.assertEquals(qs.count(), 1)

        qs = ScopedGroup.objects.all()
        self.assertEquals(qs.count(), 0)

        # create scoped group
        g2 = ScopedGroup()
        g2.name = "scopedgroup"
        g2.gid = 5000
        g2.save()

        qs = LdapGroup.objects.all()
        self.assertEquals(qs.count(), 2)

        qs = ScopedGroup.objects.all()
        self.assertEquals(qs.count(), 1)

        g2 = ScopedGroup.objects.get(name="scopedgroup")
        self.assertEquals(g2.name, u'scopedgroup')
        self.assertEquals(g2.gid, 5000)


class AdminTestCase(BaseTestCase):
    fixtures = ['test_users.json']
    directory = dict([groups, people, foouser, foogroup, bargroup])

    def setUp(self):
        super(AdminTestCase, self).setUp()
        self.client.login(username="test_user", password="password")

    def test_index(self):
        response = self.client.get('/admin/examples/')
        self.assertContains(response, "Ldap groups")
        self.assertContains(response, "Ldap users")

    def test_group_list(self):
        response = self.client.get('/admin/examples/ldapgroup/')
        self.assertContains(response, "Ldap groups")
        self.assertContains(response, "foogroup")
        self.assertContains(response, "1000")

        # order by name
        response = self.client.get('/admin/examples/ldapgroup/?o=1')
        self.assertContains(response, "Ldap groups")
        self.assertContains(response, "foogroup")
        self.assertContains(response, "1000")

        # order by gid
        response = self.client.get('/admin/examples/ldapgroup/?o=2')
        self.assertContains(response, "Ldap groups")
        self.assertContains(response, "foogroup")
        self.assertContains(response, "1000")

    def test_group_detail(self):
        response = self.client.get('/admin/examples/ldapgroup/foogroup/', follow=True)
        self.assertContains(response, "foogroup")
        self.assertContains(response, "1000")

    def test_group_add(self):
        response = self.client.post('/admin/examples/ldapgroup/add/',
                                    {'gid': '1002', 'name': 'wizgroup'})
        self.assertRedirects(response, '/admin/examples/ldapgroup/')
        qs = LdapGroup.objects.all()
        self.assertEquals(qs.count(), 3)

    def test_group_delete(self):
        response = self.client.post(
            '/admin/examples/ldapgroup/foogroup/delete/', {'yes': 'post'})
        self.assertRedirects(response, '/admin/examples/ldapgroup/')
        qs = LdapGroup.objects.all()
        self.assertEquals(qs.count(), 1)

    def test_group_search(self):
        response = self.client.get('/admin/examples/ldapgroup/?q=foo')
        self.assertContains(response, "Ldap groups")
        self.assertContains(response, "foogroup")
        self.assertContains(response, "1000")

    def test_user_list(self):
        response = self.client.get('/admin/examples/ldapuser/')
        self.assertContains(response, "Ldap users")
        self.assertContains(response, "foouser")
        self.assertContains(response, "2000")

        # order by username
        response = self.client.get('/admin/examples/ldapuser/?o=1')
        self.assertContains(response, "Ldap users")
        self.assertContains(response, "foouser")
        self.assertContains(response, "2000")

        # order by uid
        response = self.client.get('/admin/examples/ldapuser/?o=2')
        self.assertContains(response, "Ldap users")
        self.assertContains(response, "foouser")
        self.assertContains(response, "2000")

    def test_user_detail(self):
        response = self.client.get('/admin/examples/ldapuser/foouser/', follow=True)
        self.assertContains(response, "foouser")
        self.assertContains(response, "2000")

    def test_user_delete(self):
        response = self.client.post('/admin/examples/ldapuser/foouser/delete/',
                                    {'yes': 'post'})
        self.assertRedirects(response, '/admin/examples/ldapuser/')
