#!/usr/bin/python
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QComboBox,
                             QSpinBox, QDoubleSpinBox, QLabel, QPushButton,
                             QCheckBox, QLineEdit, QScrollArea, QWidget)
from PyQt5.QtCore import Qt, pyqtSlot
from functools import partial


class QEncoderConfigDlg(QDialog):
    def __init__(self, encoder, *args, **kwargs):
        super(QEncoderConfigDlg, self).__init__(*args, **kwargs)

        self.encoder = encoder

        self.setWindowTitle(f"Configure {self.encoder.codec} settings")
        self.setMinimumWidth(540)

        self.bitrateSpinBox = QSpinBox()
        self.bitrateSpinBox.setMinimum(0)
        self.bitrateSpinBox.setMaximum(40000)

        if encoder.bitrate is not None:
            self.bitrateSpinBox.setValue(encoder.bitrate)

        self.bitrateSpinBox.setSingleStep(100)
        self.bitrateSpinBox.valueChanged.connect(self.setBitrate)

        layout = QVBoxLayout()
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel("Bit rate (kbps)"))
        hlayout.addStretch()
        hlayout.addWidget(self.bitrateSpinBox)
        layout.addLayout(hlayout)

        self.codec_options = {}

        if encoder.avoptions is not None:
            self.populateOptions(layout)

        self.okayBtn = QPushButton("&OK")
        self.okayBtn.clicked.connect(self.applyAndClose)
        self.okayBtn.setDefault(True)
        self.cancelBtn = QPushButton("&Cancel")
        self.cancelBtn.clicked.connect(self.close)
        btnlayout3 = QHBoxLayout()
        btnlayout3.addStretch()
        btnlayout3.addWidget(self.okayBtn)
        btnlayout3.addWidget(self.cancelBtn)
        layout.addLayout(btnlayout3)
        self.setLayout(layout)
        self.isModified(False)

    def populateOptions(self, layout):
        encoder = self.encoder
        scroll = QScrollArea(self)
        layout.addWidget(scroll)
        scrollwidget = QWidget(scroll)
        scroll.setWidget(scrollwidget)
        scrolllayout = QVBoxLayout()
        scrollwidget.setLayout(scrolllayout)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setWidgetResizable(True)

        for opt in encoder.avoptions:
            if opt.type == "FLOAT":
                self.addFloatOption(opt, scrollwidget, scrolllayout)

            if opt.type == "INT":
                self.addIntOption(opt, scrollwidget, scrolllayout)

            elif opt.type == "STRING":
                self.addStrOption(opt, scrollwidget, scrolllayout)

            elif opt.type == "BOOL":
                self.addBoolOption(opt, scrollwidget, scrolllayout)

    def addFloatOption(self, opt, parent, layout=None):
        hlayout = QHBoxLayout()

        if layout is not None:
            layout.addLayout(hlayout)

        optenabled = QCheckBox(opt.name, parent)
        hlayout.addWidget(optenabled)
        optenabled.setToolTip(opt.help)

        hlayout.addStretch()

        widget = QDoubleSpinBox(parent)
        hlayout.addWidget(widget)
        widget.setDecimals(2)
        widget.setMinimum(opt.min)
        widget.setMaximum(opt.max)

        value = getattr(self.encoder, opt.name)
        widget.setEnabled(value is not None)
        optenabled.setCheckState(2 if value is not None else 0)
        widget.setValue(value if value is not None else opt.default)

        self.codec_options[opt.name] = widget

        optenabled.stateChanged.connect(
            partial(self.setOptionEnabled, opt.name, widget))
        widget.valueChanged.connect(partial(self.setOption, opt.name))

    def addIntOption(self, opt, parent, layout=None):
        value = getattr(self.encoder, opt.name)
        hlayout = QHBoxLayout()

        if layout is not None:
            layout.addLayout(hlayout)

        optenabled = QCheckBox(opt.name, parent)
        hlayout.addWidget(optenabled)
        optenabled.setToolTip(opt.help)

        hlayout.addStretch()

        if len(opt.choices):
            widget = QComboBox(parent)
            hlayout.addWidget(widget)

            for k, choice in enumerate(opt.choices):
                widget.addItem(choice.name, choice.value)

            if value is not None:
                optenabled.setCheckState(2)
                widget.setEnabled(True)

                for k, choice in enumerate(opt.choices):
                    if value == choice.value:
                        widget.setCurrentIndex(k)

            else:
                if opt.default:
                    for k, choice in enumerate(opt.choices):
                        if opt.default == choice.value:
                            widget.setCurrentIndex(k)

                widget.setEnabled(False)

            widget.currentIndexChanged.connect(
                partial(self.setOptionFromWidget, opt.name, widget))

        else:
            widget = QSpinBox(parent)
            hlayout.addWidget(widget)
            widget.setMinimum(opt.min)
            widget.setMaximum(opt.max)

            widget.setEnabled(value is not None)
            optenabled.setCheckState(2 if value is not None else 0)
            widget.setValue(value if value is not None else opt.default)

            self.codec_options[opt.name] = widget
            widget.valueChanged.connect(partial(self.setOption, opt.name))

        optenabled.stateChanged.connect(
            partial(self.setOptionEnabled, opt.name, widget))

    def addStrOption(self, opt, parent, layout=None):
        value = getattr(self.encoder, opt.name)

        hlayout = QHBoxLayout()

        if layout is not None:
            layout.addLayout(hlayout)

        optenabled = QCheckBox(opt.name, parent)
        hlayout.addWidget(optenabled)
        optenabled.setToolTip(opt.help)

        hlayout.addStretch()

        widget = QLineEdit(parent)
        hlayout.addWidget(widget)

        widget.setEnabled(value is not None)
        optenabled.setCheckState(2 if value is not None else 0)
        widget.setText(value if value is not None else opt.default)

        self.codec_options[opt.name] = widget
        optenabled.stateChanged.connect(
            partial(self.setOptionEnabled, opt.name, widget))
        widget.textChanged.connect(partial(self.setOption, opt.name))

    def addBoolOption(self, opt, parent, layout=None):
        value = getattr(self.encoder, opt.name)
        widget = QCheckBox(opt.name, parent)
        widget.setTristate(True)
        widget.setToolTip(opt.help)

        if layout is not None:
            layout.addWidget(widget)

        if value is not None:
            widget.setCheckState(2 if value else 0)

        else:
            widget.setCheckState(1)

        self.codec_options[opt.name] = widget
        widget.stateChanged.connect(
            partial(self.setOptionFromWidget, opt.name, widget))

    @pyqtSlot(str, QWidget, Qt.CheckState)
    def setOptionEnabled(self, option, widget, state):
        widget.setEnabled(state == 2)

        if state == 2:
            if isinstance(widget, QLineEdit):
                value = widget.text()

            elif isinstance(widget, (QDoubleSpinBox, QSpinBox)):
                value = widget.value()

            elif isinstance(widget, QComboBox):
                value = widget.currentData()

            setattr(self.encoder, option, value)

        elif state == 0:
            setattr(self.encoder, option, None)

        self.isModified()

    def setOption(self, option, value):
        if isinstance(value, Qt.CheckState):
            if value == 0:
                setattr(self.encoder, option, False)

            elif value == 1 and getattr(self.encoder, option) is not None:
                setattr(self.encoder, option, None)

            elif value == 2:
                setattr(self.encoder, option, True)

        else:
            setattr(self.encoder, option, value)

        self.isModified()

    def setOptionFromWidget(self, option, widget):
        if isinstance(widget, QCheckBox):
            value = widget.checkState()

        elif isinstance(widget, QLineEdit):
            value = widget.text()

        elif isinstance(widget, (QDoubleSpinBox, QSpinBox)):
            value = widget.value()

        elif isinstance(widget, QComboBox):
            value = widget.currentData()

        self.setOption(option, value)
        self.isModified()

    def setBitrate(self, value):
        if value:
            self.encoder.bitrate = value

        else:
            self.encoder.bitrate = None

        self.isModified()

    def applyAndClose(self):
        self.done(1)
        self.close()

    def isModified(self, flag=True):
        self.okayBtn.setEnabled(flag)

        if flag:
            self.cancelBtn.setText("&Cancel")

        else:
            self.cancelBtn.setText("&Close")
