# -*- coding: utf-8 -*-
"""
/***************************************************************************

                       EING GML import/export plugin

 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2022-06-09
        copyright            : (C) 2022 by Noispot Innovations
 ***************************************************************************/
"""

import os

from qgis.PyQt import uic
from qgis.PyQt import QtWidgets

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'import_plugin_dialog_base.ui'))


class ImportDialog(QtWidgets.QDialog, FORM_CLASS):

    def import_gml_path_changed(self):
        self.import_gpkg_path.setFilePath(self.import_gml_path.filePath().replace(".gml", ".gpkg"))

    def accept_import(self):
        if os.path.exists(self.import_gml_path.filePath()):
            self.accept()
        else:
            alert = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Warning, "Hiányzó fájl", "Az importálásra kiválasztott GML fájl nem létezik!")
            alert.exec_()

    def __init__(self, parent=None):
        """Constructor."""
        super(ImportDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)

        self.import_gml_path.fileChanged.connect(self.import_gml_path_changed)

        # default accept function leválasztása, és saját accept (path validációval) rácsatlakoztatása
        self.button_box.accepted.disconnect(self.accept)
        self.button_box.accepted.connect(self.accept_import)
