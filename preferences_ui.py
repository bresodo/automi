# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'pref.ui'
#
# Created by: PyQt5 UI code generator 5.10.1
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName("Dialog")
        Dialog.resize(473, 361)
        Dialog.setWindowOpacity(4.0)
        self.buttonBox = QtWidgets.QDialogButtonBox(Dialog)
        self.buttonBox.setGeometry(QtCore.QRect(0, 330, 469, 25))
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.setObjectName("buttonBox")
        self.label = QtWidgets.QLabel(Dialog)
        self.label.setGeometry(QtCore.QRect(10, 10, 67, 17))
        self.label.setObjectName("label")
        self.camera_index = QtWidgets.QLineEdit(Dialog)
        self.camera_index.setGeometry(QtCore.QRect(70, 30, 31, 25))
        self.camera_index.setObjectName("camera_index")
        self.label_2 = QtWidgets.QLabel(Dialog)
        self.label_2.setGeometry(QtCore.QRect(20, 30, 41, 17))
        self.label_2.setObjectName("label_2")
        self.blur_threshold = QtWidgets.QLineEdit(Dialog)
        self.blur_threshold.setGeometry(QtCore.QRect(230, 30, 31, 25))
        self.blur_threshold.setObjectName("blur_threshold")
        self.label_3 = QtWidgets.QLabel(Dialog)
        self.label_3.setGeometry(QtCore.QRect(150, 30, 81, 17))
        self.label_3.setObjectName("label_3")
        self.name_image = QtWidgets.QLineEdit(Dialog)
        self.name_image.setGeometry(QtCore.QRect(20, 80, 91, 25))
        self.name_image.setObjectName("name_image")
        self.label_4 = QtWidgets.QLabel(Dialog)
        self.label_4.setGeometry(QtCore.QRect(20, 60, 91, 17))
        self.label_4.setObjectName("label_4")
        self.name_video = QtWidgets.QLineEdit(Dialog)
        self.name_video.setGeometry(QtCore.QRect(150, 80, 91, 25))
        self.name_video.setObjectName("name_video")
        self.label_5 = QtWidgets.QLabel(Dialog)
        self.label_5.setGeometry(QtCore.QRect(150, 60, 91, 17))
        self.label_5.setObjectName("label_5")

        self.retranslateUi(Dialog)
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        _translate = QtCore.QCoreApplication.translate
        Dialog.setWindowTitle(_translate("Dialog", "Preferences"))
        self.label.setText(_translate("Dialog", "Camera"))
        self.label_2.setText(_translate("Dialog", "Index:"))
        self.label_3.setText(_translate("Dialog", "Threshold:"))
        self.label_4.setText(_translate("Dialog", "Image Name:"))
        self.label_5.setText(_translate("Dialog", "Video Name:"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    Dialog = QtWidgets.QDialog()
    ui = Ui_Dialog()
    ui.setupUi(Dialog)
    Dialog.show()
    sys.exit(app.exec_())

