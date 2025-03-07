# -*- coding: utf-8 -*-

from qgis.core import Qgis, QgsMessageLog
from osgeo import gdal, ogr, osr
import xml.etree.ElementTree as ET
import os.path

class XsdField:

    def __init__(self, name, type):
        self.name = name # mező neve
        self.type = type # xsd típus, pl. "eing:long-or-empty"

class XsdStructure:
    """A vazrajz.xsd alapján a GeoPackage struktúráját építi fel."""

    MESSAGE_TAG = 'GML import'
    
    DEFAULT_NAMESPACE = { "xmlns": "http://www.w3.org/2001/XMLSchema" }

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        
        self.eov_spatial_reference = osr.SpatialReference()
        self.eov_spatial_reference.ImportFromEPSG(23700)

    def get_layer_element_fields(self, layer_element, common_fields):
        """Feldolgozza a réteg node-ban található mezőket."""
        extension = layer_element.find("./xmlns:complexContent/xmlns:extension", XsdStructure.DEFAULT_NAMESPACE)
        field_elements = extension.findall("./xmlns:sequence/xmlns:element", XsdStructure.DEFAULT_NAMESPACE)

        fields = []
        
        # ha a közös mezőket is hozzá kell venni a mezőkhöz
        if 'base' in extension.attrib and extension.attrib['base'] == 'eing:CommonAttributesType':
            fields = common_fields.copy()

        for field_element in field_elements:
            fields.append(XsdField(field_element.attrib['name'], field_element.attrib['type']))

        return fields

    def find_complex_type_by_name(self, complex_type_elements, type):
        for complex_type_element in complex_type_elements:
            if complex_type_element.attrib['name'] == type:
                return complex_type_element

    def build_structure(self):
        """A vazrajz.xsd alapján felépít egy struktúrát, ami alapján létre lehet hozni a GeoPackage rétegeket."""
        xsd_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "vazrajz.xsd")
        QgsMessageLog.logMessage("Felhasznált XSD struktúra: " + xsd_path, XsdStructure.MESSAGE_TAG, level = Qgis.Info)
        
        xsd_root = ET.parse(xsd_path).getroot()
        
        self.supported_version = xsd_root.attrib['version']
        QgsMessageLog.logMessage("Támogatott GML XSD verzió: " + self.supported_version, XsdStructure.MESSAGE_TAG, level = Qgis.Info)
        
        # <element> node-ok, amiknek a [name] attribútuma a réteg neve, és <complexType> node-okra hivatkoznak
        elements = xsd_root.findall("./xmlns:element", XsdStructure.DEFAULT_NAMESPACE)
        
        # <complexType> node-ok, amikben a rétegek fieldjei (+ a közös mezők leírásai) vannak
        complex_types = xsd_root.findall("./xmlns:complexType", XsdStructure.DEFAULT_NAMESPACE)
        
        common_attributes_element = self.find_complex_type_by_name(complex_types, "CommonAttributesType")
        processed_common_attributes = self.get_layer_element_fields(common_attributes_element, [])
        
        self.layer_definitions = {}
        
        for element in elements:
            if 'substitutionGroup' in element.attrib and element.attrib['substitutionGroup'] == 'gml:_Feature':
                layer_name = element.attrib['name']
                complex_type_name = element.attrib['type'].split(':')[-1]

                complex_type = self.find_complex_type_by_name(complex_types, complex_type_name)
                self.layer_definitions[layer_name] = self.get_layer_element_fields(complex_type, processed_common_attributes)

    def get_geom_type(self, xsd_geometry_name):
        if xsd_geometry_name == 'gml:PolygonPropertyType':
            return ogr.wkbPolygon
            
        elif xsd_geometry_name == 'gml:LineStringPropertyType':
            return ogr.wkbLineString

        elif xsd_geometry_name == 'gml:PointPropertyType':
            return ogr.wkbPoint

        else:
            raise Exception("Nem támogatott XSD geometria típus: " + xsd_geometry_name)

    def get_field_type(self, xsd_field_type):
        if xsd_field_type == 'string' or xsd_field_type == 'eing:nonEmptyString':
            return ogr.OFTString

        elif xsd_field_type == 'int' or xsd_field_type == 'eing:int-or-empty':
            return ogr.OFTInteger
            
        elif xsd_field_type == 'long' or xsd_field_type == 'eing:long-or-empty':
            return ogr.OFTInteger64

        elif xsd_field_type == 'decimal' or xsd_field_type == 'eing:decimal-or-empty':
            return ogr.OFTReal

        elif xsd_field_type == 'double' or xsd_field_type == 'eing:double-or-empty':
            return ogr.OFTReal
            
        elif xsd_field_type == 'decimal' or xsd_field_type == 'eing:decimal-just-0':
            return ogr.OFTReal            

        else:
            raise Exception("Nem támogatott XSD mező típus: " + xsd_field_type) 

    def create_gpkg_layer(self, gpkg_data_source, layer_name):
        """A feldolgozott vazrajz.xsd alapján előállítja az adott réteghez tartozó GeoPackage réteget."""
        xsd_structure = self.layer_definitions[layer_name]
        
        for xsd_field in xsd_structure:
            if xsd_field.name == 'geometry':
                geom_type = self.get_geom_type(xsd_field.type)
                break

        layer = gpkg_data_source.CreateLayer(layer_name, self.eov_spatial_reference, geom_type = geom_type)

        for xsd_field in xsd_structure:
            if xsd_field.name == 'geometry':
                continue

            layer.CreateField(ogr.FieldDefn(xsd_field.name, self.get_field_type(xsd_field.type)))

        return layer
