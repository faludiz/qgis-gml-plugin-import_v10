# -*- coding: utf-8 -*-

from qgis.core import Qgis, QgsMessageLog
from osgeo import gdal, ogr, osr
import xml.etree.ElementTree as ET
import os.path
from .xsd_structure import XsdStructure

class GmlImporter:
    """GML --> GeoPackage importer"""
    
    MESSAGE_TAG = 'GML import'

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface

    def import_gml_metadata_to_gpkg(self, gml_path, gpkg_data_source, xsd_version):
        """A GML-ben található metaadatok feldolgozása és felvétele a GeoPackage-be."""
        gml_doc = ET.parse(gml_path)
        root = gml_doc.getroot()
        
        metadata_list = root.findall("./{http://www.opengis.net/gml}metaDataProperty/{http://www.opengis.net/gml}GenericMetaData/MetaDataList")
        for x in metadata_list[0]:
            gpkg_data_source.SetMetadataItem(x.tag, x.text)
            if x.tag == 'gmlID':
                QgsMessageLog.logMessage("GML azonosító: " + x.text, GmlImporter.MESSAGE_TAG, level = Qgis.Info)
            elif x.tag == 'xsdVersion':
                QgsMessageLog.logMessage("XSD verzió: " + x.text, GmlImporter.MESSAGE_TAG, level = Qgis.Info)
                
                if x.text != xsd_version:
                    raise Exception("A támogatott XSD verzió (" + GmlImporter.SUPPORTED_XSD_VERSION + ") nem egyezik meg az importálandó GML XSD verziójával (" + x.text + ")!") 

    def import_to_geopackage(self, gml_path, gpkg_path):
        ogr.UseExceptions()
        
        gml_data_source = ogr.GetDriverByName('gml').Open(gml_path) # a konvertálandó GML
        converted_gpkg_data_source = ogr.GetDriverByName('gpkg').CreateDataSource(gpkg_path) # a GML-ből átkonvertált GeoPackage fájl

        xsd_structure = XsdStructure(self.iface)
        xsd_structure.build_structure()

        try:
            self.import_gml_metadata_to_gpkg(gml_path, converted_gpkg_data_source, xsd_structure.supported_version)

            for layer_name in xsd_structure.layer_definitions:
                gml_layer = gml_data_source.GetLayer(layer_name)
                copied_gpkg_layer = xsd_structure.create_gpkg_layer(converted_gpkg_data_source, layer_name)

                if gml_layer is not None:
                    gpkg_feature_def = copied_gpkg_layer.GetLayerDefn()
                    gml_layer_def = gml_layer.GetLayerDefn() # a GML fájlból hiányozhatnak mezők, így annak egy másik struktúrája van

                    # GML rétegen található feature-ök átmásolása
                    for gml_feature in gml_layer:
                        converted_feature = ogr.Feature(gpkg_feature_def)
                        converted_feature.SetGeometry(gml_feature.GetGeometryRef().Clone())

                        # fieldek átmásolása
                        for i in range(gpkg_feature_def.GetFieldCount()):
                            field_name = gpkg_feature_def.GetFieldDefn(i).GetName()
                            
                            if gml_layer_def.GetFieldIndex(field_name) != -1: # csak akkor másoljuk át, ha a GML fájlban is megtalálható az adott mező
                                converted_feature.SetField(field_name, gml_feature.GetField(field_name))

                        copied_gpkg_layer.CreateFeature(converted_feature) # hozzáadás az átmásolt GeoPackage réteghez
                        del converted_feature

                QgsMessageLog.logMessage(layer_name + " réteg átmásolásra került " + str(copied_gpkg_layer.GetFeatureCount()) + " db feature-rel.", GmlImporter.MESSAGE_TAG, level = Qgis.Info)
                del copied_gpkg_layer

            del converted_gpkg_data_source # referencia megszüntetése a fájl mentéséhez
            
            self.iface.messageBar().pushMessage("Sikeres GML import", gml_path + " sikeresen beolvasásra került.", level = Qgis.Success, duration = 5)
        except Exception as err:
            converted_gpkg_data_source.Release() # lock felszabadítás
            del converted_gpkg_data_source # referencia megszüntetése

            os.remove(gpkg_path)

            QgsMessageLog.logMessage("Sikertelen GML megnyitás: " + str(err), GmlImporter.MESSAGE_TAG, level = Qgis.Critical)
            self.iface.messageBar().pushMessage("Sikertelen GML import", "Nem sikerült beimportálni az alábbi GML fájlt: " + gml_path, level = Qgis.Critical, duration = 5)