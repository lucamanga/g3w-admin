# coding=utf-8
""""Test for G3W suite QgsServer proxy

.. note:: This program is free software; you can redistribute it and/or modify
          it under the terms of the Mozilla Public License 2.0.

"""

__author__ = 'elpaso@itopen.it'
__date__ = '2020-04-07'
__copyright__ = 'Copyright 2020, Gis3w'


from django.core.management import call_command
from django.core.files import File
from django.test import Client, override_settings
from django.urls import reverse
from qgis.core import QgsProject
from core.models import G3WSpatialRefSys
from core.models import Group as CoreGroup
from qdjango.apps import QGS_SERVER, get_qgs_project
from qdjango.models import Project
from .base import QdjangoTestBase, CURRENT_PATH, TEST_BASE_PATH, QGS310_WIDGET_FILE, QgisProject
import json

from unittest import skip


@override_settings(CACHES = {
        'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'some',
        }
    },
    LANGUAGE_CODE='en',
    LANGUAGES=(
        ('en', 'English'),
    )
)
class OwsTest(QdjangoTestBase):
    """Test proxy to QgsServer"""

    @classmethod
    def setUpTestData(cls):

        super().setUpTestData()
        cls.qdjango_project = Project(
            qgis_file=cls.project.qgisProjectFile,
            title='Test qdjango project',
            group=cls.project_group,
        )
        cls.qdjango_project.save()

        qgis_project_file_widget = File(open('{}{}{}'.format(CURRENT_PATH, TEST_BASE_PATH, QGS310_WIDGET_FILE), 'r'))
        cls.project_widget310 = QgisProject(qgis_project_file_widget)
        cls.project_widget310.title = 'A project with widget QGIS 3.10'
        cls.project_widget310.group = cls.project_group
        cls.project_widget310.save()

    def test_get_qgs_project(self):
        """test get_qgs_project"""

        qgs_project = get_qgs_project(self.qdjango_project.qgis_file.path)
        self.assertTrue(isinstance(qgs_project, QgsProject))
        qgs_project = self.qdjango_project.qgis_project
        self.assertTrue(isinstance(qgs_project, QgsProject))

    def test_get(self):
        """Test get request"""

        ows_url = reverse('OWS:ows', kwargs={'group_slug': self.qdjango_project.group.slug, 'project_type': 'qdjango',
                                             'project_id': self.qdjango_project.id})

        # Make a request to the server
        c = Client()
        self.assertTrue(c.login(username='admin01', password='admin01'))
        response = c.get(ows_url, {
            'REQUEST': 'GetCapabilities',
            'SERVICE': 'WMS'
        })

        self.assertTrue(b'<Name>bluemarble</Name>' in response.content)

    def test_get_getfeatureinfo(self):
        """Test GetFeatureInfo for QGIS widget"""

        c = Client()
        self.assertTrue(c.login(username='admin01', password='admin01'))
        ows_url = reverse('OWS:ows', kwargs={'group_slug': self.project_widget310.instance.group.slug,
                                             'project_type': 'qdjango',
                                             'project_id': self.project_widget310.instance.pk})

        # test GetFeatureInfo
        response = c.get(ows_url, {
            'SERVICE': "WMS",
            'VERSION': "1.3.0",
            'REQUEST': "GetFeatureInfo",
            'CRS': "EPSG:4326",
            'LAYERS': "main_layer",
            'QUERY_LAYERS': "main_layer",
            'INFO_FORMAT': "application/json",
            'FEATURE_COUNT': "5",
            'FI_POINT_TOLERANCE': "10",
            'FI_LINE_TOLERANCE': "10",
            'FI_POLYGON_TOLERANCE': "10",
            'G3W_TOLERANCE': "0.0001259034459559036",
            'WITH_GEOMETRY': "1",
            'I': "300",
            'J': "438",
            'DPI': "96",
            'WIDTH': "600",
            'HEIGHT': "877",
            'STYLES': "",
            'BBOX': "43.78646121799684,11.249447715470794,43.79750295020717,11.257001922228149"
        })

        self.assertEqual(response.status_code, 200)
        jresponse = json.loads(response.content)

        features = jresponse['features']
        self.assertEqual(features[0]['properties']['code'], 200)
        self.assertEqual(features[0]['properties']['date'], '2020-05-19')
        self.assertEqual(features[0]['properties']['name'], 'olive')
        self.assertEqual(features[0]['properties']['type'], 'TYPE B')

    def test_getprintalias(self):
        """Test get request GetPrintAtlas"""

        ows_url = reverse('OWS:ows',
                          kwargs={'group_slug': self.project310.instance.group.slug,
                                  'project_type': 'qdjango',
                                  'project_id': self.project310.instance.id}
                          )

        # Make a request to the server
        # check for request error

        c = Client()
        self.assertTrue(c.login(username='admin01', password='admin01'))

        response = c.get(ows_url, {
            'REQUEST': 'GetPrintAtlas',
            'SERVICE': 'WMS'
        })

        self.assertEqual(response.status_code, 400)
        jres = json.loads(response.content)
        self.assertEqual(jres, {'status': 'fail', 'message': "{}: {}".format(
            "ATLAS - Error from the user while generating the PDF",
            "TEMPLATE is required."
        )})

        response = c.get(ows_url, {
            'REQUEST': 'GetPrintAtlas',
            'SERVICE': 'WMS',
            'TEMPLATE': 'atlas_test',
            'FIDS_FILTER': '1,a'
        })

        self.assertEqual(response.status_code, 400)
        jres = json.loads(response.content)
        self.assertEqual(jres, {'status': 'fail', 'message': "{}: {}".format(
            "ATLAS - Error from the user while generating the PDF",
            "FIDS_FILTER must contains only numbers."
        )})


        response = c.get(ows_url, {
            'REQUEST': 'GetPrintAtlas',
            'SERVICE': 'WMS',
            'TEMPLATE': 'atlas_test'
        })

        print (response.content)
        self.assertEqual(response.status_code, 400)
        jres = json.loads(response.content)
        self.assertEqual(jres, {'status': 'fail', 'message': "{}: {}".format(
            "ATLAS - Error from the user while generating the PDF",
            "EXP_FILTER or FIDS_FILTER are mandatory to print an atlas layout"
        )})

        response = c.get(ows_url, {
            'REQUEST': 'GetPrintAtlas',
            'SERVICE': 'WMS',
            'TEMPLATE': 'atlas_test',
            'FIDS_FILTER': '1,2',
            'EXP_FILTER': "ISOCODE IN ('IT','FR')"
        })

        self.assertEqual(response.status_code, 400)
        jres = json.loads(response.content)
        self.assertEqual(jres, {'status': 'fail', 'message': "{}: {}".format(
            "ATLAS - Error from the user while generating the PDF",
            "FIDS_FILTER and EXP_FILTER can not be used together."
        )})

        response = c.get(ows_url, {
            'REQUEST': 'GetPrintAtlas',
            'SERVICE': 'WMS',
            'TEMPLATE': 'atlas_test',
            'EXP_FILTER': "ISOCODE IN ('IT','FR')"
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

        # FIXME: why get an QgsLayoutExporter.IteratorError only on running test?
        # response = c.get(ows_url, {
        #     'REQUEST': 'GetPrintAtlas',
        #     'SERVICE': 'WMS',
        #     'TEMPLATE': 'atlas_test',
        #     'FIDS_FILTER': "1"
        # })
        #
        # self.assertEqual(response.status_code, 200)
        # self.assertEqual(response['Content-Type'], 'application/pdf')

        # remove because dimention change by context where test running.
        #self.assertEqual(len(response.content), 2807526)






