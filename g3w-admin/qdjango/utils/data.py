# -*- encoding: utf-8 -*-
from django.conf import settings
from django.http.request import QueryDict
from defusedxml import lxml
from lxml import etree
from django.utils.translation import ugettext, ugettext_lazy as _
from django.db import transaction
from qdjango.models import Project
from core.utils.data import XmlData
from .structure import *
import os, re
import json
import logging

logger = logging.getLogger('g3wadmin.debug')


def makeDatasource(datasource, layerType):
    """
    Rebuild datasource on qgjango/g3w-admin settings
    :param datasource:
    :param layerType:
    :return: string, new datasource
    """
    newDatasource = None
    # Path and folder name
    basePath = settings.DATASOURCE_PATH.rstrip('/') # eg: /home/sit/charts
    folder = os.path.basename(basePath) # eg: charts
    # OGR example datasource:
    # Original: <datasource>\\SIT-SERVER\sit\charts\definitivo\d262120.shp</datasource>
    # Modified: <datasource>/home/sit/charts\definitivo\d262120.shp</datasource>
    if layerType == Layer.TYPES.ogr or layerType == Layer.TYPES.gdal:
        newDatasource = re.sub(r'(.*?)%s(.*)' % folder, r'%s\2' % basePath, datasource) # ``?`` means ungreedy
        newDatasource = newDatasource.split('|')[0]

    # SpatiaLite example datasource:
    # Original: <datasource>dbname='//SIT-SERVER/sit/charts/Carte stradali\\naturalearth_110m_physical.sqlite' table="ne_110m_glaciated_areas" (geom) sql=</datasource>
    # Modified: <datasource>dbname='/home/sit/charts/Carte stradali\\naturalearth_110m_physical.sqlite' table="ne_110m_glaciated_areas" (geom) sql=</datasource>
    if layerType == Layer.TYPES.spatialite:
        oldPath = re.sub(r"(.*)dbname='(.*?)'(.*)", r"\2", datasource) # eg: "//SIT-SERVER/sit/charts/Carte stradali\\naturalearth_110m_physical.sqlite"
        newPath = re.sub(r'(.*?)%s(.*)' % folder, r'%s\2' % basePath, oldPath) # eg: "\home\sit\charts/Carte stradali\\naturalearth_110m_physical.sqlite" (``?`` means ungreedy)
        newDatasource = datasource.replace(oldPath, newPath)

    return newDatasource


class QgisValidator(object):
    """
    Interface for Qgis object validators
    """
    def clean(self):
        pass


class QgisProjectLayerValidator(QgisValidator):
    """
    A simple qgis project layer validator call clean method
    """

    def __init__(self, qgisProjectLayer):
        self.qgisProjectLayer = qgisProjectLayer

    def clean(self):
        pass


class DatasourceExists(QgisProjectLayerValidator):
    """
    Check if layer datasource exists on server
    """
    def clean(self):
        if self.qgisProjectLayer.layerType in [Layer.TYPES.gdal, Layer.TYPES.ogr, Layer.TYPES.raster]:
            if not os.path.exists(self.qgisProjectLayer.datasource):
                err = ugettext('Missing data file for layer {} '.format(self.qgisProjectLayer.name))
                err += ugettext('which should be located at {}'.format(self.qgisProjectLayer.datasource))
                raise Exception(err)


class ColoumnName(QgisProjectLayerValidator):
    """
    Check coloumn data name: no whitespace, no special charts.
    """
    def clean(self):
        if self.qgisProjectLayer.layerType in [Layer.TYPES.ogr, Layer.TYPES.postgres, Layer.TYPES.spatialite]:
            columns_err = []
            for column in self.qgisProjectLayer.columns:
                # search
                #rex = '[^A-Za-z0-9]+'
                rex = '[;:,%@$^&*!#()\[\]\{\}\\n\\r\\s]+'
                if re.search(rex, column['name']):
                    columns_err.append(column['name'])
            if columns_err:
                err = ugettext('The follow fields name of layer {} contains '
                               'white spaces and/or special characters: {}')\
                    .format(self.qgisProjectLayer.name, ', '.join(columns_err))
                err += ugettext('Please use \'Alias\' fields in QGIS project')
                raise Exception(err)


class QgisProjectLayer(XmlData):
    """
    Qgisdata object for layer project: a layer xml wrapper
    """

    _dataToSet = [
        'layerId',
        'isVisible',
        'title',
        'layerType',
        'minScale',
        'maxScale',
        'scaleBasedVisibility',
        'srid',
        #'capabilities',
        'wfsCapabilities',
        'editOptions',
        'datasource',
        'name',
        'origname',
        'aliases',
        'columns',
        'excludeAttributesWMS',
        'excludeAttributesWFS',
        'geometrytype'
    ]

    _introMessageException = 'Missing or invalid layer data'

    _defaultValidators = [
        DatasourceExists,
        ColoumnName
    ]

    def __init__(self, layerTree, **kwargs):
        self.qgisProjectLayerTree = layerTree

        if 'qgisProject' in kwargs:
            self.qgisProject = kwargs['qgisProject']

        if 'order' in kwargs:
            self.order = kwargs['order']

        # set data value into this object
        self.setData()

        # register default validator
        self.validators = []
        for validator in self._defaultValidators:
            self.registerValidator(validator)


    def _getDataName(self):
        """
        Get name form datasource
        :return: string
        """

        try:
            name = self.qgisProjectLayerTree.find('shortname').text
            if not name:
                raise Exception
        except:
            name = self.qgisProjectLayerTree.find('layername').text
        return name

    def _getDataOrigname(self):
        if self.layerType == Layer.TYPES.ogr or self.layerType == Layer.TYPES.gdal:
            name = os.path.splitext(os.path.basename(self.datasource))[0]
        elif self.layerType == Layer.TYPES.postgres or self.layerType == Layer.TYPES.spatialite:
            dts = datasource2dict(self.datasource)
            name = dts['table'].split('.')[-1].replace("\"", "")
        elif self.layerType ==Layer.TYPES.wms:
            dts = QueryDict(self.datasource)
            name = dts['layers']
        else:
            name = self.qgisProjectLayerTree.find('layername').text

        return name

    def _getDataLayerId(self):
        """
        Get name tag content from xml
        :return: string
        """
        logger.debug('RECUPERO ID LAYER')
        layer_id = self.qgisProjectLayerTree.find('id').text
        logger.debug(layer_id)
        return layer_id

    def _getDataTitle(self):
        """
        Get title tag content from xml
        :return: string
        """
        try:
            layer_title = self.qgisProjectLayerTree.find('layername').text
        except:
            layer_title = ''

        if layer_title == None:
            layer_title = ''

        return layer_title


    def _getDataIsVisible(self):
        """
        Get if is visible form xml
        :return: string
        """
        legendTrees = self.qgisProject.qgisProjectTree.find('legend')
        legends = legendTrees.iterdescendants(tag='legendlayerfile')

        for legend in legends:
            if legend.attrib['layerid'] == self.layerId:
                if legend.attrib['visible'] == '1':
                    return True
                else:
                    return False
        return False

    def _getDataLayerType(self):
        """
        Get name tag content from xml
        :return: string
        """
        availableTypes = [item[0] for item in Layer.TYPES]
        layerType = self.qgisProjectLayerTree.find('provider').text
        if not layerType in availableTypes:
            raise Exception(_('Missing or invalid type for layer')+' "%s"' % self.name)
        return layerType

    def _getDataMinScale(self):
        """
        Get min_scale from layer attribute
        :return: string
        """
        return int(float(self.qgisProjectLayerTree.attrib['maximumScale']))

    def _getDataMaxScale(self):
        """
        Get min_scale from layer attribute
        :return: string
        """
        return int(float(self.qgisProjectLayerTree.attrib['minimumScale']))

    def _getDataScaleBasedVisibility(self):
        """
        Get scale based visibility property from layer attribute
        :return: string
        """
        return bool(int(self.qgisProjectLayerTree.attrib['hasScaleBasedVisibilityFlag']))

    def _getDataSrid(self):
        """
        Get srid property of layer
        :return: string
        """
        try:
            srid = self.qgisProjectLayerTree.xpath('srs/spatialrefsys/srid')[0].text
        except:
            srid = None

        return int(srid)

    def _getDataCapabilities(self):
        return 1


    def _getDataGeometrytype(self):
        """
        Get geometry from layer attribute
        :return: string
        """
        return self.qgisProjectLayerTree.attrib.get('geometry')

    def _getDataEditOptions(self):

        editOptions = 0
        for editOp, layerIds in self.qgisProject.wfstLayers.items():
            if self.layerId in layerIds:
                editOptions |= getattr(settings, editOp)

        return None if editOptions == 0 else editOptions

    def _getDataWfsCapabilities(self):

        wfsCapabilities = 0
        for wfslayer in self.qgisProject.wfsLayers:
            if self.layerId in wfslayer:
                wfsCapabilities = settings.QUERYABLE

        return None if wfsCapabilities == 0 else wfsCapabilities

    def _getDataDatasource(self):
        """
        Get name tag content from xml
        :return: string
        """
        logger.debug('-DATASOURCE')
        datasource = self.qgisProjectLayerTree.find('datasource').text
        serverDatasource = makeDatasource(datasource, self.layerType)

        if serverDatasource is not None:
            return serverDatasource
        else:
            return datasource

    def _getDataAliases(self):
        """
        Get properties fields aliasies
        :return: string
        """
        logger.debug('-ALIASIES')
        ret = {}
        aliases = self.qgisProjectLayerTree.find('aliases')
        if aliases:
            for alias in aliases:
                ret[alias.attrib['field']] = alias.attrib['name']
        return ret

    def _getDataColumns(self):
        """
        Retrive data about columns for db table or ogr lyer type
        :return:
        """
        logger.debug('-COLUMNS')
        if self.layerType in [Layer.TYPES.postgres, Layer.TYPES.spatialite]:
            layerStructure = QgisDBLayerStructure(self, layerType=self.layerType)
        elif self.layerType in [Layer.TYPES.ogr]:
            layerStructure = QgisOGRLayerStructure(self)
        elif self.layerType in [Layer.TYPES.wms, Layer.TYPES.gdal]:
            return None


        if len(layerStructure.columns) > 0:
            layerStructure.columns += self._getLayerJoinedColumns()

        # add aliases
        if bool(self.aliases):
            self._addAliesToColumns(layerStructure.columns)

        return layerStructure.columns


    def _addAliesToColumns(self,columns):

        for column in columns:
            if column['name'] in self.aliases:
                column['label'] = self.aliases[column['name']] if self.aliases[column['name']] != "" else column['name']


    def _getLayerJoinedColumns(self):
        """
        Add joined columns as qgis project
        """

        # todo: review for label and other compatibilities
        joined_columns = []
        try:
            joins = self.qgisProjectLayerTree.find('vectorjoins')
            for join in joins:
                join_id = join.attrib['joinLayerId']

                # prendo l'elemento parent di un tag "id" dove il testo corrisponde al nome del layer
                joined_layer = self.qgisProjectLayerTree.getroottree().xpath('//id[text()="'+join_id+'"]/..')[0]
                joined_columns += []
        except Exception as e:
            pass
        return joined_columns

    def _getDataExcludeAttributesWMS(self):
        """
        Get attribute to exlude from WMS info and relations 
        """
        logger.debug('-EXCLUDEATRIBUTEWMS')
        excluded_columns = []
        try:
            attributes = self.qgisProjectLayerTree.find('excludeAttributesWMS')
            for attribute in attributes:
                excluded_columns.append(attribute.text)
        except Exception as e:
            pass
        return excluded_columns if excluded_columns else None

    def _getDataExcludeAttributesWFS(self):
        """
        Get attribute to exlude from WMS info and relations 
        """
        logger.debug('EXCLUDEATRIBUTEWFS')
        excluded_columns = []
        try:
            attributes = self.qgisProjectLayerTree.find('excludeAttributesWFS')
            for attribute in attributes:
                excluded_columns.append(attribute.text)
        except Exception as e:
            pass
        return excluded_columns if excluded_columns else None

    def clean(self):
        for validator in self.validators:
            validator.clean()

    def save(self):
        """
        Save o update layer instance into db
        :param instance:
        :param kwargs:
        :return:
        """

        columns = json.dumps(self.columns) if self.columns else None
        excludeAttributesWMS = json.dumps(self.excludeAttributesWMS) if self.excludeAttributesWMS else None
        excludeAttributesWFS = json.dumps(self.excludeAttributesWFS) if self.excludeAttributesWFS else None

        self.instance, created = Layer.objects.get_or_create(
            name=self.name,
            qgs_layer_id=self.layerId,
            project=self.qgisProject.instance,
            defaults={
                'origname': self.origname,
                'title': self.title,
                'is_visible': self.isVisible,
                'layer_type': self.layerType,
                'qgs_layer_id': self.layerId,
                'min_scale': self.minScale,
                'max_scale': self.maxScale,
                'scalebasedvisibility': self.scaleBasedVisibility,
                'database_columns': columns,
                'srid': self.srid,
                'datasource': self.datasource,
                'order': self.order,
                'edit_options': self.editOptions,
                'wfscapabilities': self.wfsCapabilities,
                'exclude_attribute_wms': excludeAttributesWMS,
                'exclude_attribute_wfs': excludeAttributesWFS,
                'geometrytype': self.geometrytype
                }
            )
        if not created:
            self.instance.origname = self.origname
            self.instance.title = self.title
            self.instance.is_visible = self.isVisible
            self.instance.layer_type = self.layerType
            self.instance.qgs_layer_id = self.layerId
            self.instance.min_scale = self.minScale
            self.instance.max_scale = self.maxScale
            self.instance.scalebasedvisibility = self.scaleBasedVisibility
            self.instance.datasource = self.datasource
            self.instance.database_columns = columns
            self.instance.srid = self.srid
            self.instance.order = self.order
            self.instance.edit_options = self.editOptions
            self.instance.wfscapabilities = self.wfsCapabilities
            self.instance.exclude_attribute_wms = excludeAttributesWMS
            self.instance.exclude_attribute_wfs = excludeAttributesWFS
            self.instance.geometrytype = self.geometrytype
        # Save self.instance
        self.instance.save()


class QgisProjectValidator(QgisValidator):
    """
    A simple qgis project validator call clean method
    """
    def __init__(self, qgisProject):
        self.qgisProject = qgisProject

    def clean(self):
       pass


class IsGroupCompatibleValidator(QgisProjectValidator):
    """
    Check il project is compatible with own group
    """
    def clean(self):
        if self.qgisProject.group.srid.srid != self.qgisProject.srid:
            raise Exception(_('Project and group SRID must be the same'))


class ProjectExists(QgisProjectValidator):
    """
    Check if project exists in database
    """
    def clean(self):
        from qdjango.models import Project
        if Project.objects.filter(title=self.qgisProject.title).exists():
            raise Exception(_('A project with the same title already exists'))


class ProjectTitleExists(QgisProjectValidator):
    """
    Check if project title exists
    """
    def clean(self):
        if not self.qgisProject.title:
            raise Exception(_('Title project not empty'))


class UniqueLayername(QgisProjectValidator):
    """
    Check if laeryname is unique inside a project
    """
    def clean(self):
        layers = []
        for layer in self.qgisProject.layers:
            if layer.name in layers:
                raise Exception(_('More than one layer with same name/shortname: {}'.format(layer.name)))
            layers.append(layer.name)


class CheckMaxExtent(QgisProjectValidator):
    """
    Check il WMSExtent is correct
    """
    def clean(self):
        max_extent = self.qgisProject.maxExtent
        if max_extent:

            # check is a cordinate il None or empty
            wrong_coord = list()
            for coord, value in max_extent.items():
                if not value:
                    wrong_coord.append(coord)

            if len(wrong_coord) > 0:
                raise Exception(_('Check WMS start extent project property: {} didn\'t set'.format(','.join(wrong_coord))))

            # check calue are correct inside angles coordinates
            err_msg_x = err_msg_y = ''
            if max_extent['xmax'] < max_extent['xmin']:
                err_msg_x = _('xmax smaller then xmin ')
            if max_extent['ymax'] < max_extent['ymin']:
                err_msg_y = _('ymax smaller then ymin ')

            if err_msg_x or err_msg_y:
                raise Exception('Check WMS start extent project property: {}{}'.format(err_msg_x, err_msg_y))


class QgisProject(XmlData):
    """
    A qgis xml project file wrapper
    """
    _dataToSet = [
        'name',
        'title',
        'srid',
        'units',
        'initialExtent',
        'maxExtent',
        'wfsLayers',
        'wfstLayers',
        'layersTree',
        'layers',
        'layerRelations',
        'qgisVersion',
        ]

    _defaultValidators = [
        IsGroupCompatibleValidator,
        ProjectTitleExists,
        UniqueLayername,
        CheckMaxExtent
    ]

    #_regexXmlLayer = 'projectlayers/maplayer[@geometry!="No geometry"]'

    _regexXmlLayer = 'projectlayers/maplayer'

    _introMessageException = _('Invalid Project Data ')

    def __init__(self, qgis_file, **kwargs):
        self.qgisProjectFile = qgis_file
        self.validators = []
        self.instance = None

        #istance of a model Project
        if 'instance' in kwargs:
            self.instance = kwargs['instance']

        if 'group' in kwargs:
            self.group = kwargs['group']

        for k in ['thumbnail', 'description', 'baselayer']:
            setattr(self, k, kwargs[k] if k in kwargs else None)


        # try to load xml project file
        self.loadProject()

        # set data value into this object
        self.setData()

        #register defaul validator
        for validator in self._defaultValidators:
            self.registerValidator(validator)

    def loadProject(self):
        """
        Load projectfile by xml parser
        """
        try:

            # we have to rewind the underlying file in case it has been already parsed
            self.qgisProjectFile.file.seek(0)
            self.qgisProjectTree = lxml.parse(self.qgisProjectFile, forbid_entities=False)
        except Exception as e:
            raise Exception(_('The project file is malformed: {}'.format(e.message)))


    def _getDataName(self):
        """
        Get projectname from xml
        :return: string
        """
        return self.qgisProjectTree.getroot().attrib['projectname']

    def _getDataTitle(self):
        """
        Get title tag content from xml
        :return: string
        """
        return self.qgisProjectTree.find('title').text

    def _getDataInitialExtent(self):
        """
        Get start extention project from xml
        :return: dict
        """
        return {
            'xmin': self.qgisProjectTree.find('mapcanvas/extent/xmin').text,
            'ymin': self.qgisProjectTree.find('mapcanvas/extent/ymin').text,
            'xmax': self.qgisProjectTree.find('mapcanvas/extent/xmax').text,
            'ymax': self.qgisProjectTree.find('mapcanvas/extent/ymax').text
        }

    def _getDataMaxExtent(self):
        """
        Get max extention project from xml wms extent
        :return: dict
        """
        wmsExtent = self.qgisProjectTree.find('properties/WMSExtent')
        if wmsExtent is not None:
            coordsEls = wmsExtent.getchildren()
            xmin = coordsEls[0].text
            ymin = coordsEls[1].text
            xmax = coordsEls[2].text
            ymax = coordsEls[3].text

            return {
                'xmin': xmin,
                'ymin': ymin,
                'xmax': xmax,
                'ymax': ymax
            }
        else:
            return None


    def _getDataSrid(self):
        """

        :return:
        """
        return int(self.qgisProjectTree.find('mapcanvas/destinationsrs/spatialrefsys/srid').text)

    def _getDataUnits(self):
        return self.qgisProjectTree.find('mapcanvas/units').text

    def _checkLayerTypeCompatible(self,layerTree):
        """
        Chek il layer is compatible for to show in webgis
        :param layerTree:
        :return:
        """
        if 'name' in layerTree.attrib:
            if layerTree.attrib['name'] == 'openlayers':
                return False
        if 'embedded' in layerTree.attrib:
            if layerTree.attrib['embedded'] == '1':
                return False
        return True

    def _getDataLayersTree(self):

        #get root of layer-tree-group
        layerTreeRoot = self.qgisProjectTree.find('layer-tree-group')

        def buildLayerTreeNodeObject(layerTreeNode):
            toRetLayers = []
            for level, layerTreeSubNode in enumerate(layerTreeNode):
                if level > 0:



                    toRetLayer = {
                        'name': layerTreeSubNode.attrib['name'],
                        'expanded': True if layerTreeSubNode.attrib['expanded'] == '1' else False
                    }

                    if layerTreeSubNode.tag == 'layer-tree-group':

                        mutually_exclusive = False
                        if 'mutually-exclusive' in layerTreeSubNode.attrib and \
                                        layerTreeSubNode.attrib['mutually-exclusive'] == '1':
                            mutually_exclusive = True

                        mutually_exclusive_child = False
                        if 'mutually-exclusive-child' in layerTreeSubNode.attrib and \
                                        layerTreeSubNode.attrib['mutually-exclusive-child'] == '1':
                            mutually_exclusive_child = True

                        toRetLayer.update({
                            'mutually-exclusive': mutually_exclusive,
                            'mutually-exclusive-child': mutually_exclusive_child
                        })

                    if layerTreeSubNode.tag == 'layer-tree-layer':
                        toRetLayer.update({
                            'id': layerTreeSubNode.attrib['id'],
                            'visible': True if layerTreeSubNode.attrib['checked'] == 'Qt::Checked' else False
                        })

                    if layerTreeSubNode.tag == 'layer-tree-group':
                        toRetLayer.update({
                            'nodes': buildLayerTreeNodeObject(layerTreeSubNode)
                        })
                    toRetLayers.append(toRetLayer)
            return toRetLayers

        return buildLayerTreeNodeObject(layerTreeRoot)

    def _getDataLayers(self):
        layers = []

        # Get layer trees
        layerTrees = self.qgisProjectTree.xpath(self._regexXmlLayer)

        for order, layerTree in enumerate(layerTrees):
            if self._checkLayerTypeCompatible(layerTree):
                layers.append(QgisProjectLayer(layerTree, qgisProject=self, order=order))
        return layers

    def _getDataLayerRelations(self):
        """
        Get relations layer section into project
        :param layerTree:
        :return:
        """
        # get root of layer-tree-group
        layerRelationsRoot = self.qgisProjectTree.find('relations')
        layer_realtions = []
        for order, layer_relation in enumerate(layerRelationsRoot):
            attrib = dict(layer_relation.attrib)

            # add fieldRef
            field_ref = layer_relation.find('fieldRef')
            attrib['fieldRef'] = field_ref.attrib
            layer_realtions.append(attrib)

        return layer_realtions if layer_realtions else None

    def _getDataQgisVersion(self):
        """
        Get Qgisversion project
        :return:
        """
        return self.qgisProjectTree.getroot().attrib['version']

    def _getDataWfsLayers(self):
        """
        Return a array of wfslayers
        """

        wfsLayersTree = self.qgisProjectTree.xpath('properties/WFSLayers/value')
        wfsLayers = []
        for wfsLayer in wfsLayersTree:
            wfsLayers.append(wfsLayer.text)

        return wfsLayers

    def _getDataWfstLayers(self):
        wfstLayers = {
            'INSERT': [],
            'UPDATE': [],
            'DELETE': []
        }

        wfstLayersTree = self.qgisProjectTree.xpath('properties/WFSTLayers')[0]

        # collect layer_id for edito ps
        for editOp in wfstLayers.keys():
            editOpsLayerIdsTree = wfstLayersTree.xpath('{}/value'.format(editOp.lower().capitalize()))
            for editOpsLayerIdTree in editOpsLayerIdsTree:
                wfstLayers[editOp].append(editOpsLayerIdTree.text)

        return wfstLayers


    def clean(self):
        for validator in self.validators:
            validator.clean()

        for layer in self.layers:
            layer.clean()

    def save(self, instance=None, **kwargs):
        """
        Save or update  qgisporject and layers into db
        :param instance: Project instance
        """

        with transaction.atomic():
            if not instance and not self.instance:

                thumbnail = kwargs.get('thumbnail')
                description = kwargs.get('description')
                baselayer = kwargs.get('baselayer')

                self.instance = Project.objects.create(
                    qgis_file=self.qgisProjectFile,
                    group=self.group,
                    title=self.title,
                    initial_extent=self.initialExtent,
                    max_extent=self.maxExtent,
                    thumbnail=thumbnail,
                    description=description,
                    baselayer=baselayer,
                    qgis_version=self.qgisVersion,
                    layers_tree=self.layersTree,
                    relations=self.layerRelations
                )
            else:
                if instance:
                    self.instance = instance
                self.instance.qgis_file = self.qgisProjectFile
                self.instance.title = self.title
                self.instance.qgis_version = self.qgisVersion
                self.instance.initial_extent = self.initialExtent
                self.instance.max_extent = self.maxExtent
                self.instance.layers_tree = self.layersTree
                self.instance.relations = self.layerRelations

                self.instance.save()

            # Create or update layers
            for layer in self.layers:
                layer.save()

            # Pre-existing layers that have not been updated must be dropped
            newLayerNameList = [(layer.name, layer.datasource) for layer in self.layers]
            for layer in self.instance.layer_set.all():
                if (layer.name, layer.datasource) not in newLayerNameList:
                    layer.delete()

            # Update qgis file datasource for SpatiaLite and OGR layers
            self.updateQgisFileDatasource()

    def updateQgisFileDatasource(self):
        """Update qgis file datasource for SpatiaLite and OGR layers.

        SpatiaLite and OGR layers need their datasource string to be
        modified at import time so that the original path is replaced with
        the DjangoQGIS one (which is stored in ``settings.py`` as variable
        ``DATASOURCE_PATH``).

        Example original datasource::

        <datasource>\\SIT-SERVER\sit\charts\definitivo\d262120.shp</datasource>

        Example modified datasource::

        <datasource>/home/sit/charts\definitivo\d262120.shp</datasource>
        """

        # Parse the file and build the XML tree
        self.instance.qgis_file.file.seek(0)
        tree = lxml.parse(self.instance.qgis_file, forbid_entities=False)

        # Run through the layer trees
        for layer in tree.xpath(self._regexXmlLayer):
            if self._checkLayerTypeCompatible(layer):
                layerType = layer.find('provider').text
                datasource = layer.find('datasource').text

                newDatasource = makeDatasource(datasource,layerType)

                # Update layer
                if newDatasource:
                    layer.find('datasource').text = newDatasource

        # Update QGIS file
        with open(self.instance.qgis_file.path, 'w') as handler:
            tree.write(handler)


class QgisProjectSettingsWMS(XmlData):

    _dataToSet = [
        'layers',
        'composerTemplates'
    ]

    _NS = {
        'opengis': 'http://www.opengis.net/wms'
    }

    def __init__(self, project_settings, **kwargs):
        self.qgisProjectSettingsFile = project_settings

        # load data
        self.loadProjectSettings()

        # set data
        self.setData()

    def loadProjectSettings(self):
        """
        Load from 'string'  wms response request getProjectSettings
        :return:
        """
        try:
            self.qgisProjectSettingsTree = lxml.fromstring(self.qgisProjectSettingsFile)
        except Exception as e:
            raise Exception(
                _('The project settings is malformed: {} ----- {}'.format(e.message, self.qgisProjectSettingsFile)))

    def _buildTagWithNS(self, tag):
        return '{{{0}}}{1}'.format(self._NS['opengis'], tag)

    def _getBBOXLayer(self, layerTree):

        bboxes = {}

        bboxTrees = layerTree.xpath(
            'opengis:BoundingBox',
            namespaces=self._NS
        )

        for bboxTree in bboxTrees:
            bboxes[bboxTree.attrib['CRS']] = {
                'minx': float(bboxTree.attrib['minx']),
                'miny': float(bboxTree.attrib['miny']),
                'maxx': float(bboxTree.attrib['maxx']),
                'maxy': float(bboxTree.attrib['maxy']),
            }

        return bboxes

    def _getLayerTreeData(self, layerTree):

        subLayerTrees = layerTree.xpath('opengis:Layer', namespaces=self._NS)
        if subLayerTrees:
            for subLayerTree in subLayerTrees:
                self._getLayerTreeData(subLayerTree)
        else:
            name = layerTree.find(self._buildTagWithNS('Name')).text
            title = layerTree.find(self._buildTagWithNS('Title')).text
            dataLayer = {
                'name': name,
                'title': title,
                'visible': bool(int(layerTree.attrib['visible'])),
                'queryable': bool(int(layerTree.attrib['queryable'])),
                'bboxes': self._getBBOXLayer(layerTree)
            }
            self._layersData[name] = dataLayer

    def _getDataLayers(self):

        self._layersData = {}

        layersTree = self.qgisProjectSettingsTree.xpath(
            'opengis:Capability',
            namespaces=self._NS
        )

        self._getLayerTreeData(layersTree[0])
        return self._layersData


    def _getDataComposerTemplates(self):

        self._composerTemplatesData = []

        composerTemplates= self.qgisProjectSettingsTree.xpath(
            'opengis:Capability/opengis:ComposerTemplates/opengis:ComposerTemplate',
            namespaces=self._NS
        )
        
        _composerTemplateData = {}
        for composerTemplate in composerTemplates:
            _composerTemplateData['name'] = composerTemplate.attrib['name']
            _composerMaps = []
            for composerMap in composerTemplate.findall("opengis:ComposerMap", namespaces=self._NS):
              _composerMaps.append({
                  'name': composerMap.attrib['name'],
                  'w': float(composerMap.attrib['width']),
                  'h': float(composerMap.attrib['height'])
              })
            self._composerTemplatesData.append({
                'name': composerTemplate.attrib['name'],
                'w': composerTemplate.attrib['width'],
                'h': composerTemplate.attrib['height'],
                'maps': _composerMaps
            })

        return self._composerTemplatesData


class QgisPgConnection(object):
    """
    Postgis xml interchange file
    """
    _version = "1.0"

    _params = {
        'port':5432,
        'saveUsername':'true',
        'password':'',
        'savePassword':'true',
        'sslmode':1,
        'service':'',
        'username':'',
        'host':'',
        'database':'',
        'name':'',
        'estimatedMetadata':'false'
    }

    def __init__(self, **kwargs):

        self._data = {}
        for k,v in kwargs.items():
            setattr(self,k,v)

    def __setattr__(self, key, value):

        if key in QgisPgConnection._params.keys():
            self.__dict__['_data'][key] = value
        else:
            self.__dict__[key] = value

    def __getattr__(self, key):

        if key in QgisPgConnection._params.keys():
            try:
                return self.__dict__['_data'][key]
            except:
                return QgisPgConnection._params[key]

        return self.__dict__[key]

    def asXML(self):

        qgsPgConnectionTree = etree.Element('qgsPgConnections', version=self._version)
        postgisTree = etree.Element('postgis')
        postgisTreeAttributes = postgisTree.attrib

        for key in QgisPgConnection._params.keys():
            postgisTreeAttributes[key] = str(getattr(self, key))

        qgsPgConnectionTree.append(postgisTree)

        return etree.tostring(qgsPgConnectionTree, doctype='<!DOCTYPE connections>')


