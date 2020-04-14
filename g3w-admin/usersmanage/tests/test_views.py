# coding=utf-8
""""
    Test usermanage module views
.. note:: This program is free software; you can redistribute it and/or modify
    it under the terms of the Mozilla Public License 2.0.

"""

__author__ = 'lorenzetti@gis3w.it'
__date__ = '2020-04-14'
__copyright__ = 'Copyright 2015 - 2020, Gis3w'

from django.test import Client
from django.urls import reverse
from .base import BaseUsermanageTestCase
from .utils import setup_testing_user_relations


class UsermanageViewsTest(BaseUsermanageTestCase):

    def setUp(self) -> None:
        super(UsermanageViewsTest, self).setUp()
        setup_testing_user_relations(self)
        self.client = Client()

    def test_users(self):
        """ Test views list and other and ACL"""

        # Login required
        url = reverse('user-list')
        url_newone = reverse('user-add')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

        # Login as Admin1
        self.assertTrue(self.client.login(username=self.test_user1.username, password=self.test_user1.username))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Check object_list
        object_list = response.context_data['object_list']

        # Every test users:
        # test_user1, test_user2, test_editor1...
        self.assertEqual(len(object_list), 11)

        # Admin1 can create new user
        response = self.client.get(url_newone)
        self.assertEqual(response.status_code, 200)
        self.client.logout()

        # Login as Editor1
        self.assertTrue(self.client.login(username=self.test_editor1.username, password=self.test_editor1.username))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Check object_list
        object_list = response.context_data['object_list']

        # Every test users:
        # test_user1, test_user2, test_editor1...
        self.assertEqual(len(object_list), 0)

        # Editor1 can create new user
        response = self.client.get(url_newone)
        self.assertEqual(response.status_code, 200)
        self.client.logout()

        # Login as Editor1: test_editor1_2
        self.assertTrue(self.client.login(username=self.test_editor1_2.username, password=self.test_editor1_2.username))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Check object_list
        object_list = response.context_data['object_list']

        # Every test users:
        # test_user1, test_user2, test_editor1...
        self.assertEqual(len(object_list), 3)

        # Login as Editor2
        # only his account
        self.assertTrue(self.client.login(username=self.test_editor2.username, password=self.test_editor2.username))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Check object_list
        object_list = response.context_data['object_list']

        # Every test users:
        # test_user1, test_user2, test_editor1...
        self.assertEqual(len(object_list), 0)

        # Editor2 can't create new user
        response = self.client.get(url_newone)
        self.assertEqual(response.status_code, 403)
        self.client.logout()

        # Login as Viewer1
        # only his account
        self.assertTrue(self.client.login(username=self.test_viewer1.username, password=self.test_viewer1.username))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Viewer1 can't create new user
        response = self.client.get(url_newone)
        self.assertEqual(response.status_code, 403)
        self.client.logout()

    def test_user_groups(self):
        """ Test views list and other and ACL for user groups """

        # Login required
        url = reverse('user-group-list')
        url_newone = reverse('user-group-add')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

        # Login as Admin1
        self.assertTrue(self.client.login(username=self.test_user1.username, password=self.test_user1.username))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Check object_list
        object_list = response.context_data['object_list']

        # Every test groups:
        # test_gu_editor1, test_gu_editor2, ... , test_gu_editor1_E1_2, ...
        self.assertEqual(len(object_list), 6)

        self.client.logout()

        # Login as Editor1
        self.assertTrue(self.client.login(username=self.test_editor1.username, password=self.test_editor1.username))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Check object_list
        object_list = response.context_data['object_list']

        self.assertEqual(len(object_list), 0)

        # Editor1 can add new one
        response = self.client.get(url_newone)
        self.assertEqual(response.status_code, 200)
        self.client.logout()

        # Login as Editor2: access denied for new one
        self.assertTrue(self.client.login(username=self.test_editor2.username, password=self.test_editor2.username))
        response = self.client.get(url_newone)
        self.assertEqual(response.status_code, 403)
        self.client.logout()

        # Login as Editor1.2
        self.assertTrue(self.client.login(username=self.test_editor1_2.username, password=self.test_editor1_2.username))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Check object_list
        object_list = response.context_data['object_list']

        self.assertEqual(len(object_list), 2)
        self.client.logout()


