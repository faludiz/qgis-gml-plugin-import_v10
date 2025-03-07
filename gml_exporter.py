# -*- coding: utf-8 -*-

from qgis.core import Qgis, QgsMessageLog
from osgeo import gdal, ogr, osr

from xml.etree.ElementTree import Element, SubElement, ElementTree
import xml.etree.ElementTree as ET

class GmlExporter:
    """GeoPackage --> GML exporter"""
    
    MESSAGE_TAG = 'GML export'

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        
    def format_float(self, number):
        return str('{0:.3f}'.format(number)).rstrip('0').rstrip('.') # ".0" rész levágása, ha lenne ilyen

    def calculate_data_source_extent(self, gpkg_data_source):
        """A kapott datasource összes elemének extentje, rétegtől függetlenül."""
        x_mins, x_maxs, y_mins, y_maxs = [], [], [], []
        
        for layer_index in range(gpkg_data_source.GetLayerCount()):
            gpkg_layer = gpkg_data_source.GetLayerByIndex(layer_index)
            
            # a gpkg_layer.GetExtent() truncate-eli az extentet, ezért egyesével kell rajta végigiterálni
            for feature in gpkg_layer:
                x_min, x_max, y_min, y_max = feature.GetGeometryRef().GetEnvelope()
            
                x_mins.append(x_min)
                x_maxs.append(x_max)
                y_mins.append(y_min)
                y_maxs.append(y_max)
                
        return [min(x_mins), max(x_maxs), min(y_mins), max(y_maxs)]

    def add_geometry_element(self, layer_element, geom):
        geom_element = SubElement(layer_element, 'eing:geometry')
        geom_name = geom.GetGeometryName()

        if geom_name == 'POINT':
            point_element = SubElement(geom_element, 'gml:Point', {'srsDimension': '2', 'srsName': 'urn:x-ogc:def:crs:EPSG:23700' })
            gml_pos_element = SubElement(point_element, 'gml:pos')
            gml_pos_element.text = self.format_float(geom.GetX()) + ' ' + self.format_float(geom.GetY())
            
        elif geom_name == 'POLYGON':
            polygon_element = SubElement(geom_element, 'gml:Polygon', {'srsDimension': '2', 'srsName': 'urn:x-ogc:def:crs:EPSG:23700' })
            
            for ring_index in range(geom.GetGeometryCount()):
                gml_exterior_element = SubElement(polygon_element, 'gml:exterior' if ring_index == 0 else 'gml:interior')
                gml_linear_ring_element = SubElement(gml_exterior_element, 'gml:LinearRing', {'srsDimension': '2' })
                gml_pos_list_element = SubElement(gml_linear_ring_element, 'gml:posList')
                ring = geom.GetGeometryRef(ring_index)
                
                point_arr = []
                for i in range(0, ring.GetPointCount()):
                    eov_x, eov_y = ring.GetPoint_2D(i)
                    point_arr.append(self.format_float(eov_x) + ' ' + self.format_float(eov_y))

                gml_pos_list_element.text = ' '.join(point_arr)
            
        elif geom_name == 'LINESTRING':
            linestring_element = SubElement(geom_element, 'gml:LineString', {'srsDimension': '2', 'srsName': 'urn:x-ogc:def:crs:EPSG:23700' })
            gml_pos_list_element = SubElement(linestring_element, 'gml:posList')

            point_arr = []
            for i in range(geom.GetPointCount()):
                eov_x, eov_y = geom.GetPoint_2D(i)
                point_arr.append(self.format_float(eov_x) + ' ' + self.format_float(eov_y))

            gml_pos_list_element.text = ' '.join(point_arr)

        else:
            raise Exception("Nem támogatott geometria típus: " + geom_name) 

    def add_field_elements(self, layer_element, gml_feature, gml_layer_def, new_fid):
        """Feature attribútumok hozzáadása node-onként."""
        for i in range(gml_layer_def.GetFieldCount()):
            field_name = gml_layer_def.GetFieldDefn(i).GetName()
            field_val = gml_feature.GetField(field_name)
            
            if field_name == 'GEOBJ_ID':
                layer_element.set('gml:id', 'fid-' + str(new_fid if field_val is None else field_val))

            field_element = SubElement(layer_element, 'eing:' + field_name)
            
            # floatok esetén a ".0" rész levágása, ha lenne ilyen
            if isinstance(field_val, float):
                field_element.text = self.format_float(field_val)
                
            elif field_val is not None:
                field_element.text = str(field_val)

    def add_metadata_list_element(self, gpkg_data_source, meta_data_key, meta_data_list_element):
        meta_data_value = gpkg_data_source.GetMetadataItem(meta_data_key)
        meta_data_element = SubElement(meta_data_list_element, meta_data_key)
        meta_data_element.text = meta_data_value

    def add_metadata_element(self, root, gpkg_data_source):
        """metaDataProperty node létrehozása, valamint feltöltése a GeoPackage metaadataival."""
        meta_data_list_element = SubElement(SubElement(SubElement(root, 'gml:metaDataProperty'), 'gml:GenericMetaData'), 'MetaDataList')
        
        self.add_metadata_list_element(gpkg_data_source, 'gmlID', meta_data_list_element)
        self.add_metadata_list_element(gpkg_data_source, 'gmlExportDate', meta_data_list_element)
        self.add_metadata_list_element(gpkg_data_source, 'gmlGeobjIds', meta_data_list_element)
        self.add_metadata_list_element(gpkg_data_source, 'xsdVersion', meta_data_list_element)

    def add_envelope_element(self, root, extent):
        bounded_by_element = SubElement(root, 'gml:boundedBy')
        envelope_element = SubElement(bounded_by_element, 'gml:Envelope', { 'srsDimension': '2', 'srsName': 'urn:x-ogc:def:crs:EPSG:23700' })
        
        lower_corner_element = SubElement(envelope_element, 'gml:lowerCorner')
        lower_corner_element.text = self.format_float(extent[0]) + " " + self.format_float(extent[2])
        
        upper_corner_element = SubElement(envelope_element, 'gml:upperCorner')
        upper_corner_element.text = self.format_float(extent[1]) + " " + self.format_float(extent[3])

    def get_sorted_layer_indexes(self, gpkg_data_source):
        """
        Visszaadja a GeoPackage data source-ban található rétegek GML-ben elvárt sorrendjét.
        
        :return: Egy rendezett listával tér vissza, aminek elemei a data source rétegeinek indexei.
        """
        QgsMessageLog.logMessage('FZ: get_sorted_layer_indexes.begin', GmlExporter.MESSAGE_TAG, level = Qgis.Info);
        
        indexes = []
        
        QgsMessageLog.logMessage('FZ: gpkg_data_source.GetLayerCount='+gpkg_data_source.GetLayerCount(), GmlExporter.MESSAGE_TAG, level = Qgis.Info);
        
        for layer_index in range(gpkg_data_source.GetLayerCount()):
            gpkg_layer = gpkg_data_source.GetLayerByIndex(layer_index)

            if gpkg_layer.GetFeatureCount() > 0:
                indexes.append((gpkg_layer.GetNextFeature().GetField('RETEG_ID'), layer_index))
                gpkg_layer.ResetReading()
            
        # indexes.sort(reverse = True)
        indexes = indexes.sort(reverse = True)
        
        QgsMessageLog.logMessage('FZ: get_sorted_layer_indexes.indexes: OK', GmlExporter.MESSAGE_TAG, level = Qgis.Info);
        
        r = list(map(lambda x: x[1], indexes))
        
        QgsMessageLog.logMessage('FZ: get_sorted_layer_indexes.list: OK', GmlExporter.MESSAGE_TAG, level = Qgis.Info);
        
        # return list(map(lambda x: x[1], indexes)) # listát csinál a tuple-ök második eleméből, vagyis az indexből
        return r

    def export_to_gml(self, gpkg_path, gml_path):
        ogr.UseExceptions()

        try:
            gpkg_data_source = ogr.GetDriverByName('gpkg').Open(gpkg_path)
            
            QgsMessageLog.logMessage('FZ: gpkg_data_source: OK', GmlExporter.MESSAGE_TAG, level = Qgis.Info);

            root = Element('gml:FeatureCollection')
            root.set('xmlns:eing', 'eing.foldhivatal.hu')
            root.set('xmlns:gml', 'http://www.opengis.net/gml')
            
            QgsMessageLog.logMessage('FZ: root: OK', GmlExporter.MESSAGE_TAG, level = Qgis.Info);
            
            self.add_metadata_element(root, gpkg_data_source) # metadata node-ok hozzáadása
            
            QgsMessageLog.logMessage('FZ: add_metadata_element: OK', GmlExporter.MESSAGE_TAG, level = Qgis.Info);            
            
            feature_members_element = SubElement(root, 'gml:featureMembers')
            
            QgsMessageLog.logMessage('FZ: feature_members_element: OK', GmlExporter.MESSAGE_TAG, level = Qgis.Info);
            
            new_fid = 1
            
            idxs = self.get_sorted_layer_indexes(gpkg_data_source)
            QgsMessageLog.logMessage('FZ: idxs: OK', GmlExporter.MESSAGE_TAG, level = Qgis.Info);
            
            
            for layer_index in self.get_sorted_layer_indexes(gpkg_data_source):
            
                QgsMessageLog.logMessage('FZ: for layer_index: OK', GmlExporter.MESSAGE_TAG, level = Qgis.Info);
                
                gpkg_layer = gpkg_data_source.GetLayerByIndex(layer_index)
                
                QgsMessageLog.logMessage('FZ: layer: OK', GmlExporter.MESSAGE_TAG, level = Qgis.Info);
                
                layer_name = gpkg_layer.GetName()
                
                QgsMessageLog.logMessage('FZ: layername: OK', GmlExporter.MESSAGE_TAG, level = Qgis.Info);
                
                # GML rétegen található feature-ök átmásolása
                for feature in gpkg_layer:
                    layer_element = SubElement(feature_members_element, 'eing:' + layer_name)
                    
                    QgsMessageLog.logMessage('FZ: layer_element: OK', GmlExporter.MESSAGE_TAG, level = Qgis.Info);

                    self.add_envelope_element(layer_element, feature.GetGeometryRef().GetEnvelope()) # envelope node hozzáadása
                    
                    QgsMessageLog.logMessage('FZ: add_envelope_element: OK', GmlExporter.MESSAGE_TAG, level = Qgis.Info);
                    
                    self.add_field_elements(layer_element, feature, gpkg_layer.GetLayerDefn(), new_fid) # field node-ok hozzáadása
                    
                    QgsMessageLog.logMessage('FZ: add_field_elements: OK', GmlExporter.MESSAGE_TAG, level = Qgis.Info);
                    
                    self.add_geometry_element(layer_element, feature.GetGeometryRef()) # geometry node hozzáadása
                    
                    QgsMessageLog.logMessage('FZ: add_geometry_element: OK', GmlExporter.MESSAGE_TAG, level = Qgis.Info);
                    
                    new_fid += 1

            tree = ElementTree(root)
            
            QgsMessageLog.logMessage('FZ: tree: OK', GmlExporter.MESSAGE_TAG, level = Qgis.Info);
            
            tree.write(gml_path, xml_declaration = True, encoding = 'UTF-8')
            
            QgsMessageLog.logMessage('FZ: tree.write: OK', GmlExporter.MESSAGE_TAG, level = Qgis.Info);
            
            self.iface.messageBar().pushMessage("Sikeres GML export", "A GeoPackage fájl sikeresen exportálásra került az alábbi helyre: " + gml_path, level = Qgis.Success, duration = 5)
        except Exception as err:
            QgsMessageLog.logMessage("Sikertelen GML export: " + str(err), GmlExporter.MESSAGE_TAG, level = Qgis.Critical)
            self.iface.messageBar().pushMessage("Sikertelen GML export", "Nem sikerült exportálni az alábbi GeoPackage fájlt: " + gpkg_path, level = Qgis.Critical, duration = 5)
