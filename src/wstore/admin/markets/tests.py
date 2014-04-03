# -*- coding: utf-8 -*-

# Copyright (c) 2013 CoNWeT Lab., Universidad Politécnica de Madrid

# This file is part of WStore.

# WStore is free software: you can redistribute it and/or modify
# it under the terms of the European Union Public Licence (EUPL)
# as published by the European Commission, either version 1.1
# of the License, or (at your option) any later version.

# WStore is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# European Union Public Licence for more details.

# You should have received a copy of the European Union Public Licence
# along with WStore.
# If not, see <https://joinup.ec.europa.eu/software/page/eupl/licence-eupl>.

import json
import types
from urllib2 import HTTPError
from mock import MagicMock
from nose_parameterized import parameterized

from django.test import TestCase

from wstore.admin.markets import markets_management
from wstore.models import Marketplace
from wstore.admin.markets import views
from wstore.store_commons.utils.testing import decorator_mock, build_response_mock,\
decorator_mock_callable, HTTPResponseMock


__test__ = False


class FakeMarketAdaptor():

    def __init__(self, url):
        pass

    def add_service(self, store, info):
        pass

    def delete_service(self, store, ser):
        pass

    def add_store(self, store_info):
        if store_info['store_uri'] == 'http://currentsiteerr.com':
            raise HTTPError('site', 500, 'Internal server error', None, None)

    def delete_store(self, store):
        pass


class RegisteringOnMarketplaceTestCase(TestCase):

    tags = ('fiware-ut-7',)
    fixtures = ['reg_mark.json']

    @classmethod
    def setUpClass(cls):
        markets_management.MarketAdaptor = FakeMarketAdaptor
        super(RegisteringOnMarketplaceTestCase, cls).setUpClass()

    def test_basic_registering_on_market(self):

        markets_management.register_on_market('test_market', 'http://testmarket.com', 'http://currentsite.com')

        market = Marketplace.objects.get(name='test_market')

        self.assertEqual(market.name, 'test_market')
        self.assertEqual(market.host, 'http://testmarket.com/')

    def test_registering_already_registered(self):

        try:
            markets_management.register_on_market('test_market', 'http://testmarket.com', 'http://currentsiteerr.com')
        except Exception, e:
            error = True
            msg = e.message

        self.assertTrue(error)
        self.assertEquals(msg, 'Bad Gateway')

    def test_registering_existing_name(self):

        error = False
        try:
            markets_management.register_on_market('test_market1', 'http://testmarket.com', 'http://currentsite.com')
        except Exception, e:
            error = True
            msg = e.message

        self.assertTrue(error)
        self.assertEquals(msg, 'Marketplace name already in use')


class MarketPlacesRetievingTestCase(TestCase):

    fixtures = ['get_mark.json']

    def test_basic_retrieving_of_markets(self):

        markets = markets_management.get_marketplaces()

        self.assertEquals(len(markets), 3)
        self.assertEquals(markets[0]['name'], 'test_market1')
        self.assertEquals(markets[0]['host'], 'http://examplemarketplace1.com/')
        self.assertEquals(markets[1]['name'], 'test_market2')
        self.assertEquals(markets[1]['host'], 'http://examplemarketplace2.com/')
        self.assertEquals(markets[2]['name'], 'test_market3')
        self.assertEquals(markets[2]['host'], 'http://examplemarketplace3.com/')


class UnregisteringFromMarketplaceTestCase(TestCase):

    tags = ('fiware-ut-8',)
    fixtures = ['del_mark.json']

    @classmethod
    def setUpClass(cls):
        markets_management.MarketAdaptor = FakeMarketAdaptor
        super(UnregisteringFromMarketplaceTestCase, cls).setUpClass()

    def test_basic_unregistering_from_market(self):

        markets_management.unregister_from_market('test_market')

        market = Marketplace.objects.all()
        self.assertEquals(len(market), 0)

    def test_unregistering_already_unregistered(self):

        error = False
        try:
            markets_management.unregister_from_market('test_market1')
        except:
            error = True

        self.assertTrue(error)


class MarketplaceViewTestCase(TestCase):

    tags = ('market-view',)

    @classmethod
    def setUpClass(cls):
        from wstore.store_commons.utils import http
        # Save the reference of the decorators
        cls._old_auth = types.FunctionType(
            http.authentication_required.func_code,
            http.authentication_required.func_globals,
            name=http.authentication_required.func_name,
            argdefs=http.authentication_required.func_defaults,
            closure=http.authentication_required.func_closure
        )

        cls._old_supp = types.FunctionType(
            http.supported_request_mime_types.func_code,
            http.supported_request_mime_types.func_globals,
            name=http.supported_request_mime_types.func_name,
            argdefs=http.supported_request_mime_types.func_defaults,
            closure=http.supported_request_mime_types.func_closure
        )

        # Mock class decorators
        http.authentication_required = decorator_mock
        http.supported_request_mime_types = decorator_mock_callable

        reload(views)
        views.build_response = build_response_mock

        # Mock get_current_site methods
        views.get_current_site = MagicMock()
        site_obj = MagicMock()
        site_obj.domain = 'http://teststore.org'
        views.get_current_site.return_value = site_obj
        super(MarketplaceViewTestCase, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        # Restore mocked decorators
        from wstore.store_commons.utils import http
        http.authentication_required = cls._old_auth
        http.supported_request_mime_types = cls._old_supp
        super(MarketplaceViewTestCase, cls).tearDownClass()

    def setUp(self):
        # Mock market management methods
        views.register_on_market = MagicMock()
        self.request = MagicMock()

    def _forbidden(self):
        self.request.user.is_staff = False

    def _market_failure(self):
        views.register_on_market.side_effect = Exception('Bad Gateway')

    def _bad_request(self):
        views.register_on_market.side_effect = Exception('Bad request')

    @parameterized.expand([
    ({
        'name': 'test_market',
        'host': 'http://testmarket.com'
    }, (201, 'Created', 'correct'), False),
    ({
        'name': 'test_market',
        'host': 'http://testmarket.com'
    }, (403, 'Forbidden', 'error'), True, _forbidden),
    ({
        'invalid': 'test_market',
        'host': 'http://testmarket.com'
    }, (400, 'Request body is not valid JSON data', 'error'), True),
    ({
        'name': 'test_market',
        'host': 'http://testmarket.com'
    }, (502, 'Bad Gateway', 'error'), True, _market_failure),
    ({
        'name': 'test_market',
        'host': 'http://testmarket.com'
    }, (400, 'Bad request', 'error'), True, _bad_request)
    ])
    def test_market_api_create(self, data, exp_resp, error, side_effect=None):
        # Create request data
        self.request.raw_post_data = json.dumps(data)

        if side_effect:
            side_effect(self)

        # Create the view
        market_collection = views.MarketplaceCollection(permitted_methods=('POST', 'GET'))

        response = market_collection.create(self.request)

        # Check response
        content = json.loads(response.content)
        self.assertEquals(response.status_code, exp_resp[0])
        self.assertEquals(content['message'], exp_resp[1])
        self.assertEquals(content['result'], exp_resp[2])

        # Check calls
        if not error:
            views.register_on_market.assert_called_with(data['name'], data['host'], 'http://teststore.org')

    def test_market_api_get(self):
        pass
