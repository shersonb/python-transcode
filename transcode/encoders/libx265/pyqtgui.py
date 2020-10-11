#!/usr/bin/python
from fractions import Fraction as QQ
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QComboBox, QGridLayout,
                             QSpinBox, QDoubleSpinBox, QLabel, QPushButton, QCheckBox, QLineEdit,
                             QScrollArea, QWidget, QTabWidget)
from PyQt5.QtGui import QRegExpValidator, QFont
from PyQt5.QtCore import Qt, QRegExp, pyqtSignal, pyqtSlot
import regex
from functools import partial

class Choices(QWidget):
    def __init__(self, encoder, optname, attrname, choices, *args, **kwargs):
        super(Choices, self).__init__(*args, **kwargs)
        self.encoder = encoder
        self.optname = optname
        self.attrname = attrname

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.label = QLabel(optname, self)
        layout.addWidget(self.label)

        layout.addStretch()

        self.selection = QComboBox(self)
        layout.addWidget(self.selection)

        self.selection.addItem("Not set", None)
        self.selection.insertSeparator(1)

        currentvalue = getattr(encoder, attrname)

        for choice in choices:
            if isinstance(choice, (list, tuple)):
                name, value, *_ = choice

            elif isinstance(choice, str):
                name = value = choice

            elif isinstance(choice, int):
                value = choice
                name = f"{choice}"

            self.selection.addItem(name, value)

            if currentvalue == value:
                self.selection.setCurrentIndex(self.selection.count() - 1)

        self.selection.currentIndexChanged.connect(self.indexChanged)

    def indexChanged(self, value):
        data = self.selection.currentData()
        setattr(self.encoder, self.attrname, data)

class IntOption(QWidget):
    def __init__(self, encoder, optname, attrname, minval, maxval, step, *args, **kwargs):
        super(IntOption, self).__init__(*args, **kwargs)
        self.encoder = encoder
        self.optname = optname
        self.attrname = attrname

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.label = QLabel(optname, self)
        layout.addWidget(self.label)

        layout.addStretch()

        self.spinbox = QSpinBox(self)
        layout.addWidget(self.spinbox)

        self.spinbox.setSpecialValueText("Not set")
        self.spinbox.setMinimum(minval)
        self.spinbox.setMaximum(maxval)
        self.spinbox.setSingleStep(step)

        currentvalue = getattr(encoder, attrname)

        if currentvalue is not None:
            self.spinbox.setValue(currentvalue)

        else:
            self.spinbox.setValue(minval)

        self.spinbox.valueChanged.connect(self.valueChanged)

    def valueChanged(self, value):
        if value > self.spinbox.minimum():
            setattr(self.encoder, self.attrname, value)

        else:
            setattr(self.encoder, self.attrname, None)

class FloatOption(QWidget):
    def __init__(self, encoder, optname, attrname, minval, maxval, step, decimals, *args, **kwargs):
        super(FloatOption, self).__init__(*args, **kwargs)
        self.encoder = encoder
        self.optname = optname
        self.attrname = attrname

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.label = QLabel(optname, self)
        layout.addWidget(self.label)

        layout.addStretch()

        self.spinbox = QDoubleSpinBox(self)
        layout.addWidget(self.spinbox)

        self.spinbox.setSpecialValueText("Not set")
        self.spinbox.setMinimum(minval)
        self.spinbox.setMaximum(maxval)
        self.spinbox.setDecimals(decimals)
        self.spinbox.setSingleStep(step)

        currentvalue = getattr(encoder, attrname)

        if currentvalue is not None:
            self.spinbox.setValue(currentvalue)

        else:
            self.spinbox.setValue(minval)

        self.spinbox.valueChanged.connect(self.valueChanged)

    def valueChanged(self, value):
        if value > self.spinbox.minimum() + 10**-6:
            setattr(self.encoder, self.attrname, value)

        else:
            setattr(self.encoder, self.attrname, None)

class BoolOption(QCheckBox):
    def __init__(self, encoder, optname, attrname, *args, **kwargs):
        super(BoolOption, self).__init__(*args, **kwargs)
        self.encoder = encoder
        self.setText(optname)
        self.attrname = attrname
        self.setTristate(True)

        currentvalue = getattr(encoder, attrname)

        if currentvalue is not None:
            self.setCheckState(2 if currentvalue else 0)

        else:
            self.setCheckState(1)

        self.stateChanged.connect(self.setOpt)

    def setOpt(self, state):
        if state == 0:
            setattr(self.encoder, self.attrname, False)

        elif state == 2:
            setattr(self.encoder, self.attrname, True)

        else:
            setattr(self.encoder, self.attrname, None)

class PerformanceTab(QWidget):
    optionchanged = pyqtSignal()

    def __init__(self, encoder, *args, **kwargs):
        super(PerformanceTab, self).__init__(*args, **kwargs)
        layout = QVBoxLayout()
        layout.setSpacing(4)
        self.setLayout(layout)
        """
        --preset, -p <integer|string>
        --tune, -t <string>
        --slices <integer>
        --copy-pic, --no-copy-pic
        --asm <integer:false:string>, --no-asm
        --frame-threads, -F <integer>
        --pools <string>, --numa-pools <string>
        --wpp, --no-wpp
        --pmode, --no-pmode
        --pme, --no-pme
        """
        self.preset = Choices(encoder, "Preset", "preset", 
                                 ["ultrafast", "superfast", "veryfast", "faster", "fast",
                                  "medium", "slow", "slower", "veryslow", "placebo"], self)
        self.preset.selection.currentIndexChanged.connect(self.optionchanged.emit)
        self.preset.setToolTip("--preset, -p <integer|string>\n\n"\
            "Sets parameters to preselected values, trading off compression efficiency\n"\
            "against encoding speed. These parameters are applied before all other input\n"\
            "parameters are applied, and so you can override any parameters that these\n"\
            "values control.")
        layout.addWidget(self.preset)

        self.tune = Choices(encoder, "Tune", "tune", 
                        ["None", "psnr", "ssim", "grain", "zerolatency", "fast-decode", "animation"], self)
        self.tune.selection.currentIndexChanged.connect(self.optionchanged.emit)
        self.tune.setToolTip("--tune, -t <string>\n\n"\
            "Tune the settings for a particular type of source or situation. The changes will\n"\
            "be applied after --preset but before all other parameters. Default none.")
        layout.addWidget(self.tune)

        ### TODO: Insert --asm

        self.framethreads = IntOption(encoder, "Frame Threads", "frame-threads", -1, 16, 1, self)
        self.framethreads.spinbox.valueChanged.connect(self.optionchanged.emit)
        self.framethreads.setToolTip("--frame-threads, -F <integer>\n\n"\
            "Number of concurrently encoded frames. Using a single frame thread gives a\n"\
            "slight improvement in compression, since the entire reference frames are always\n"\
            "available for motion compensation, but it has severe performance implications.\n"\
            "Default is an autodetected count based on the number of CPU cores and whether\n"\
            "WPP is enabled or not.\n\n"\
            "Over-allocation of frame threads will not improve performance, it will generally just\n"\
            "increase memory use.\n\n"\
            "Values: any value between 0 and 16. Default is 0, auto-detect")
        layout.addWidget(self.framethreads)

        ### TODO: Insert --pools, --numa-pools


        self.slices = IntOption(encoder, "Slices", "slices", 0, 16, 1, self)
        self.slices.spinbox.valueChanged.connect(self.optionchanged.emit)
        self.slices.setToolTip("--slices <integer>\n\n"\
            "Encode each incoming frame as multiple parallel slices that may be decoded\n"\
            "independently. Support available only for rectangular slices that cover the\n"\
            "entire width of the image.\n\n"\
            "Recommended for improving encoder performance only if frame-parallelism\n"\
            "and WPP are unable to maximize utilization on given hardware.\n\n"\
            "Default: 1 slice per frame. Experimental feature.")
        layout.addWidget(self.slices)

        self.wpp = BoolOption(encoder, "Wavefront Parallel Processing", "wpp", self)
        self.wpp.stateChanged.connect(self.optionchanged.emit)
        layout.addWidget(self.wpp)

        self.pmode = BoolOption(encoder, "Parallel Mode Decision", "pmode", self)
        self.pmode.stateChanged.connect(self.optionchanged.emit)
        layout.addWidget(self.pmode)

        self.pme = BoolOption(encoder, "Parallel Motion Estimation", "pme", self)
        self.pme.stateChanged.connect(self.optionchanged.emit)
        layout.addWidget(self.pme)

        self.copypic = BoolOption(encoder, "Copy Picture", "copy-pic", self)
        self.copypic.stateChanged.connect(self.optionchanged.emit)
        layout.addWidget(self.copypic)
        layout.addStretch()

class ModeDecisionAnalysisTab(QWidget):
    optionchanged = pyqtSignal()

    def __init__(self, encoder, *args, **kwargs):
        super(ModeDecisionAnalysisTab, self).__init__(*args, **kwargs)
        layout = QVBoxLayout()
        layout.setSpacing(4)
        self.setLayout(layout)

        self.rd = IntOption(encoder, "RDO Level", "rd", 0, 6, 1, self)
        self.rd.spinbox.valueChanged.connect(self.optionchanged.emit)
        self.rd.setToolTip("--rd <1..6>\n\n"\
            "Level of RDO in mode decision. The higher the value, the more exhaustive\n"\
            "the analysis and the more rate distortion optimization is used. The lower the\n"\
            "value the faster the encode, the higher the value the smaller the bitstream\n"\
            "(in general). Default 3")
        layout.addWidget(self.rd)

        self.ctu = Choices(encoder, "Maximum CU Size", "ctu", [16, 32, 64], self)
        self.ctu.selection.currentIndexChanged.connect(self.optionchanged.emit)
        self.ctu.setToolTip("--ctu, -s <64|32|16>\n\n"\
            "Maximum CU size (width and height). The larger the maximum CU size, the\n"\
            "more efficiently x265 can encode flat areas of the picture, giving large\n"\
            "reductions in bitrate. However this comes at a loss of parallelism with fewer\n"\
            "rows of CUs that can be encoded in parallel, and less frame parallelism as well.\n"\
            "Because of this the faster presets use a CU size of 32. Default: 64")
        layout.addWidget(self.ctu)

        self.mincusize = Choices(encoder, "Minimum CU Size", "min-cu-size", [8, 16, 32], self)
        self.mincusize.selection.currentIndexChanged.connect(self.optionchanged.emit)
        self.mincusize.setToolTip("--min-cu-size <32|16|8>\n\n"\
            "Minimum CU size (width and height). By using 16 or 32 the encoder will not\n"\
            "analyze the cost of CUs below that minimum threshold, saving considerable\n"\
            "amounts of compute with a predictable increase in bitrate. This setting has a\n"\
            "large effect on performance on the faster presets.\n\n"\
            "Default: 8 (minimum 8x8 CU for HEVC, best compression efficiency)")
        layout.addWidget(self.mincusize)

        self.limitrefs = IntOption(encoder, "Limit References", "limit-refs", -1, 3, 1, self)
        self.limitrefs.spinbox.valueChanged.connect(self.optionchanged.emit)
        self.limitrefs.setToolTip("--limit-refs <0|1|2|3>\n\n"\
            "When set to X265_REF_LIMIT_DEPTH (1) x265 will limit the references\n"\
            "analyzed at the current depth based on the references used to code the 4\n"\
            "sub-blocks at the next depth. For example, a 16x16 CU will only use the\n"\
            "references used to code its four 8x8 CUs.\n\n"\
            "When set to X265_REF_LIMIT_CU (2), the rectangular and asymmetrical\n"\
            "partitions will only use references selected by the 2Nx2N motion search\n"\
            "(including at the lowest depth which is otherwise unaffected by the depth\n"\
            "limit).\n\n"\
            "When set to 3 (X265_REF_LIMIT_DEPTH && X265_REF_LIMIT_CU), the\n"\
            "2Nx2N motion search at each depth will only use references from the split\n"\
            "CUs and the rect/amp motion searches at that depth will only use the\n"\
            "reference(s) selected by 2Nx2N.\n\n"\
            "For all non-zero values of limit-refs, the current depth will evaluate intra mode\n"\
            "(in inter slices), only if intra mode was chosen as the best mode for atleast one\n"\
            "of the 4 sub-blocks.\n\n"\
            "You can often increase the number of references you are using (within your\n"\
            "decoder level limits) if you enable one or both of these flags.\n\n"\
            "Default 3.")
        layout.addWidget(self.limitrefs)

        layout.addStretch()

class SliceDecisionTab(QWidget):
    optionchanged = pyqtSignal()

    def __init__(self, encoder, *args, **kwargs):
        super(SliceDecisionTab, self).__init__(*args, **kwargs)
        layout = QVBoxLayout()
        layout.setSpacing(4)
        self.setLayout(layout)

        self.opengop = BoolOption(encoder, "Open GOP", "open-gop", self)
        self.opengop.stateChanged.connect(self.optionchanged.emit)
        self.opengop.setToolTip("--open-gop, --no-open-gop\n\n"\
            "Enable open GOP, allow I-slices to be non-IDR. Default enabled.")
        layout.addWidget(self.opengop)

        self.keyint = IntOption(encoder, "Maximum Keyframe Interval", "keyint", 0, 1440, 1, self)
        self.keyint.spinbox.valueChanged.connect(self.optionchanged.emit)
        self.keyint.setToolTip("--keyint, -I <integer>\n\n"\
            "Max intra period in frames. A special case of infinite-gop (single keyframe at\n"\
            "the beginning of the stream) can be triggered with argument -1. Use 1 to force\n"\
            "all-intra. When intra-refresh is enabled it specifies the interval between which\n"\
            "refresh sweeps happen. Default 250.")
        layout.addWidget(self.keyint)

        self.minkeyint = IntOption(encoder, "Minimum Keyframe Interval", "min-keyint", 0, 1440, 1, self)
        self.minkeyint.spinbox.valueChanged.connect(self.optionchanged.emit)
        self.minkeyint.setToolTip("--min-keyint, -i <integer>\n\n"\
            "Minimum GOP size. Scenecuts beyond this interval are coded as IDR and start a\n"\
            "new keyframe, while scenecuts closer together are coded as I or P. For fixed\n"\
            "keyframe interval, set value to be equal to keyint.\n\n"\
            "Range of values: >=0 (0: auto).")
        layout.addWidget(self.minkeyint)

        self.scenecut = IntOption(encoder, "Scenecut threshold", "scenecut", -1, 100, 1, self)
        self.scenecut.spinbox.valueChanged.connect(self.optionchanged.emit)
        self.scenecut.setToolTip("--scenecut <integer>, --no-scenecut\n\n"\
            "How aggressively I-frames need to be inserted. The higher the threshold value,\n"\
            "the more aggressive the I-frame placement. --scenecut 0 or --no-scenecut disables\n"\
            "adaptive I frame placement. Default 40.")
        layout.addWidget(self.scenecut)

        self.scenecutbias = FloatOption(encoder, "Scenecut Bias", "scenecut-bias", -0.1, 100, 1, 1, self)
        self.scenecutbias.spinbox.valueChanged.connect(self.optionchanged.emit)
        self.scenecutbias.spinbox.setSuffix("%")
        self.scenecutbias.setToolTip("--scenecut-bias <0..100.0>\n\n"\
            "This value represents the percentage difference between the inter cost and intra\n"\
            "cost of a frame used in scenecut detection. For example, a value of 5 indicates, if\n"\
            "the inter cost of a frame is greater than or equal to 95 percent of the intra cost of\n"\
            "the frame, then detect this frame as scenecut. Values between 5 and 15 are\n"\
            "recommended. Default 5.")
        layout.addWidget(self.scenecutbias)

        self.rclookahead = IntOption(encoder, "RC Lookahead", "rc-lookahead", -1, 250, 1, self)
        self.rclookahead.spinbox.valueChanged.connect(self.optionchanged.emit)
        self.rclookahead.setToolTip("--rc-lookahead <integer>\n\n"\
            "Number of frames for slice-type decision lookahead (a key determining factor for\n"\
            "encoder latency). The longer the lookahead buffer the more accurate scenecut\n"\
            "decisions will be, and the more effective cuTree will be at improving adaptive quant.\n"\
            "Having a lookahead larger than the max keyframe interval is not helpful. Default 20.\n\n"\
            "Range of values: Between the maximum consecutive bframe count (--bframes) and 250.")
        layout.addWidget(self.rclookahead)

        self.goplookahead = IntOption(encoder, "GOP Lookahead", "gop-lookahead", -1, 250, 1, self)
        self.goplookahead.spinbox.valueChanged.connect(self.optionchanged.emit)
        self.goplookahead.setToolTip("--gop-lookahead <integer>\n\n"\
            "Number of frames for GOP boundary decision lookahead. If a scenecut frame is\n"\
            "found within this from the gop boundary set by –keyint, the GOP will be extented\n"\
            "until such a point, otherwise the GOP will be terminated as set by –keyint.\n"\
            "Default 0.\n\n"\
            "Range of values: Between 0 and (–rc-lookahead - mini-GOP length).\n\n"\
            "It is recommended to have –gop-lookahaed less than –min-keyint as scenecuts\n"\
            "beyond –min-keyint are already being coded as keyframes.")
        layout.addWidget(self.goplookahead)

        """
        TODO:
        --lookahead-slices
        --lookahead-threads
        --b-adaptation
        --bframes
        --bframe-bias
        --b-pyramid
        --force-flush
        --fades
        """

        layout.addStretch()

class QualityRateControlTab(QWidget):
    optionchanged = pyqtSignal()

    def __init__(self, encoder, *args, **kwargs):
        super(QualityRateControlTab, self).__init__(*args, **kwargs)
        self.encoder = encoder
        #self.config = config
        #encoderstate = config.getState(encoder)

        layout = QVBoxLayout()
        layout.setSpacing(4)
        self.setLayout(layout)

        self.rateControlSelection = QComboBox(self)
        self.rateControlSelection.addItem("Not set")
        self.rateControlSelection.insertSeparator(1)
        self.rateControlSelection.addItem("Bitrate", 0)
        self.rateControlSelection.addItem("CRF", 1)
        self.rateControlSelection.addItem("QP", 2)
        self.rateControlSelection.addItem("Lossless", 3)

        self.bitrateSpinBox = QSpinBox(self)
        self.bitrateSpinBox.setMinimum(200)
        self.bitrateSpinBox.setValue(8000)
        self.bitrateSpinBox.setSuffix("kbps")
        self.bitrateSpinBox.setMaximum(60000)
        self.bitrateSpinBox.setSingleStep(100)
        self.bitrateSpinBox.setHidden(True)

        self.crfSpinBox = QDoubleSpinBox(self)
        self.crfSpinBox.setMinimum(0)
        self.crfSpinBox.setValue(28)
        self.crfSpinBox.setMaximum(51)
        self.crfSpinBox.setSingleStep(0.1)
        self.crfSpinBox.setDecimals(2)
        self.crfSpinBox.setHidden(True)

        self.qpSpinBox = QSpinBox(self)
        self.qpSpinBox.setMinimum(0)
        self.qpSpinBox.setValue(22)
        self.qpSpinBox.setMaximum(54)
        self.qpSpinBox.setSingleStep(1)
        self.qpSpinBox.setHidden(True)

        self.rcSpacer = QWidget(self)
        self.rcSpacer.setHidden(True)

        self.bitrateSpinBox.setFixedWidth(96)
        self.crfSpinBox.setFixedWidth(96)
        self.qpSpinBox.setFixedWidth(96)
        self.rcSpacer.setFixedWidth(96)

        if encoder.bitrate is not None:
            idx = self.rateControlSelection.findData(0)
            self.rateControlSelection.setCurrentIndex(idx)
            self.bitrateSpinBox.setValue(encoder.bitrate)
            self.bitrateSpinBox.setVisible(True)

        elif encoder.crf is not None:
            idx = self.rateControlSelection.findData(1)
            self.rateControlSelection.setCurrentIndex(idx)
            self.crfSpinBox.setValue(encoder.crf)
            self.crfSpinBox.setVisible(True)

        elif encoder.qp is not None:
            idx = self.rateControlSelection.findData(2)
            self.rateControlSelection.setCurrentIndex(idx)
            self.qpSpinBox.setValue(encoder.qp)
            self.qpSpinBox.setVisible(True)

        elif encoder.lossless:
            idx = self.rateControlSelection.findData(3)
            self.rateControlSelection.setCurrentIndex(idx)

        else:
            self.rateControlSelection.setCurrentIndex(0)
            self.rcSpacer.setVisible(True)

        self.rateControlSelection.currentIndexChanged.connect(self.onRateControlModeChange)
        self.bitrateSpinBox.valueChanged.connect(self.setBitrate)
        self.crfSpinBox.valueChanged.connect(self.setCRF)
        self.qpSpinBox.valueChanged.connect(self.setQP)

        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel("Rate Control"))
        hlayout.addStretch()
        hlayout.addWidget(self.rateControlSelection)
        hlayout.addWidget(self.bitrateSpinBox)
        hlayout.addWidget(self.crfSpinBox)
        hlayout.addWidget(self.qpSpinBox)
        hlayout.addWidget(self.rcSpacer)
        layout.addLayout(hlayout)
        """
        TODO:
        --vbv-bufsize
        --vbv-maxrate
        --vbv-init
        --vbv-end
        --vbv-end-fr-adj

        --crf-max
        --crf-min

        --qpmin
        --qpmax

        --lossless

        --aq-mode
        --aq-strength
        --aq-motion
        --hevc-aq
        --qp-adaptation-range
        --qg-size
        --cutree
        --slow-firstpass
        --multi-pass-opt-analysis
        --multi-pass-opt-distortion
        --strict-cbr
        --cbqpoffs
        --crqpoffs
        --ipratio
        --pbratio
        --qcomp
        --qpstep
        --rc-grain
        --const-vbv
        --qblur
        --cplxblur
        --scenecut-aware-qp
        --scenecut-window
        --max-qp-delta
        """

        layout.addStretch()

    def onRateControlModeChange(self, index):
        data = self.rateControlSelection.currentData()

        if data == 0:
            self.encoder.bitrate = self.bitrateSpinBox.value()
            self.encoder.crf = None
            self.encoder.qp = None
            self.encoder.lossless = None

            self.crfSpinBox.setHidden(True)
            self.qpSpinBox.setHidden(True)
            self.rcSpacer.setHidden(True)
            self.bitrateSpinBox.setHidden(False)

        elif data == 1:
            self.encoder.bitrate = None
            self.encoder.crf = self.crfSpinBox.value()
            self.encoder.qp = None
            self.encoder.lossless = None

            self.bitrateSpinBox.setHidden(True)
            self.qpSpinBox.setHidden(True)
            self.rcSpacer.setHidden(True)
            self.crfSpinBox.setHidden(False)

        elif data == 2:
            self.encoder.bitrate = None
            self.encoder.crf = None
            self.encoder.qp = self.qpSpinBox.value()
            self.encoder.lossless = None

            self.bitrateSpinBox.setHidden(True)
            self.crfSpinBox.setHidden(True)
            self.rcSpacer.setHidden(True)
            self.qpSpinBox.setHidden(False)

        elif data == 3:
            self.encoder.bitrate = None
            self.encoder.crf = None
            self.encoder.qp = None
            self.encoder.lossless = True

            self.bitrateSpinBox.setHidden(True)
            self.crfSpinBox.setHidden(True)
            self.qpSpinBox.setHidden(True)
            self.rcSpacer.setHidden(False)

        else:
            self.encoder.bitrate = None
            self.encoder.crf = None
            self.encoder.qp = None
            self.encoder.lossless = None

            self.crfSpinBox.setHidden(True)
            self.qpSpinBox.setHidden(True)
            self.bitrateSpinBox.setHidden(True)
            self.rcSpacer.setHidden(False)

        self.optionchanged.emit()

    def setBitrate(self, value):
        self.encoder.bitrate = value
        self.optionchanged.emit()

    def setCRF(self, value):
        self.encoder.crf = value
        self.optionchanged.emit()

    def setQP(self, value):
        self.encoder.qp = value
        self.optionchanged.emit()

class x265ConfigDlg(QDialog):
    def __init__(self, encoder, *args, **kwargs):
        super(x265ConfigDlg, self).__init__(*args, **kwargs)
        self.encoder = encoder
        self.setFont(QFont("Dejavu Serif", 8))
        self.setWindowTitle("Configure libx265 settings")
        self.setMinimumWidth(540)

        layout = QVBoxLayout()

        self.tabs = QTabWidget(self)
        layout.addWidget(self.tabs)

        self.ratecontrol = QualityRateControlTab(encoder, self.tabs)
        self.ratecontrol.optionchanged.connect(self.isModified)
        self.tabs.addTab(self.ratecontrol, "Quality/Rate Control")

        self.performance = PerformanceTab(encoder, self.tabs)
        self.performance.optionchanged.connect(self.isModified)
        self.tabs.addTab(self.performance, "Performance")

        self.modedec = ModeDecisionAnalysisTab(encoder, self.tabs)
        self.modedec.optionchanged.connect(self.isModified)
        self.tabs.addTab(self.modedec, "Mode Decision/Analysis")

        self.sliceDecision= SliceDecisionTab(encoder, self.tabs)
        self.sliceDecision.optionchanged.connect(self.isModified)
        self.tabs.addTab(self.sliceDecision, "Slice Decision")


        #self.pltTab = QWidget(self.tabs)
        #self.tabs.addTab(self.pltTab, "Profile/Level/Tier")
        #pltLayout = QVBoxLayout()
        #self.pltTab.setLayout(pltLayout)

        #self.rateCtlTab = QWidget(self.tabs)
        #self.tabs.addTab(self.rateCtlTab, "Quality/Rate Control")
        #rateCtlLayout = QVBoxLayout()
        #self.rateCtlTab.setLayout(rateCtlLayout)

        #self.sliceDecisionTab = QWidget(self.tabs)
        #self.tabs.addTab(self.sliceDecisionTab, "Slice Decision")
        #sliceDecisionLayout = QVBoxLayout()
        #self.sliceDecisionTab.setLayout(sliceDecisionLayout)

        #self.presetSelection = QComboBox()
        #self.presetSelection.addItem("ultrafast")
        #self.presetSelection.addItem("superfast")
        #self.presetSelection.addItem("veryfast")
        #self.presetSelection.addItem("faster")
        #self.presetSelection.addItem("fast")
        #self.presetSelection.addItem("medium")
        #self.presetSelection.addItem("slow")
        #self.presetSelection.addItem("slower")
        #self.presetSelection.addItem("veryslow")
        #self.presetSelection.addItem("placebo")

        #for index in range(self.presetSelection.count()):
            #if self.presetSelection.itemText(index) == self.config.preset:
                #break
        #else:
            #index = 5
        #self.presetSelection.setCurrentIndex(index)

        #self.presetSelection.currentIndexChanged.connect(self.onPresetChange)

        #hlayout = QHBoxLayout()
        #hlayout.addWidget(QLabel("Preset"))
        #hlayout.addStretch()
        #hlayout.addWidget(self.presetSelection)
        #presetsLayout.addLayout(hlayout)



        #self.tuneSelection = QComboBox()
        #self.tuneSelection.addItem("None")
        #self.tuneSelection.addItem("psnr")
        #self.tuneSelection.addItem("ssim")
        #self.tuneSelection.addItem("grain")
        #self.tuneSelection.addItem("zerolatency")
        #self.tuneSelection.addItem("fastdecode")

        #for index in range(1, self.presetSelection.count()):
            #if self.tuneSelection.itemText(index) == self.config.tune:
                #break
        #else:
            #index = 0
        #self.tuneSelection.setCurrentIndex(index)

        #self.tuneSelection.currentIndexChanged.connect(self.onTuneChange)

        #hlayout = QHBoxLayout()
        #hlayout.addWidget(QLabel("Tune"))
        #hlayout.addStretch()
        #hlayout.addWidget(self.tuneSelection)
        #presetsLayout.addLayout(hlayout)


        #self.profileSelection = QComboBox()
        #self.profileSelection.addItem("main")
        #self.profileSelection.addItem("main10")
        #self.profileSelection.addItem("mainstillpicture")

        #for index in range(1, self.presetSelection.count()):
            #if self.profileSelection.itemText(index) == self.config.profile:
                #break
        #else:
            #index = 0
        #self.profileSelection.setCurrentIndex(index)

        #self.profileSelection.currentIndexChanged.connect(self.onProfileChange)

        ##gridlayout.addWidget(QLabel("Profile:"), 2, 0)
        ##gridlayout.addWidget(self.profileSelection, 2, 1)

        #hlayout = QHBoxLayout()
        #hlayout.addWidget(QLabel("Profile"))
        #hlayout.addStretch()
        #hlayout.addWidget(self.profileSelection)
        #pltLayout.addLayout(hlayout)



        #self.aqModeSelection = QComboBox()
        ##self.aqModeSelection.setMaximumWidth(128)
        #self.aqModeSelection.addItem("None")
        #self.aqModeSelection.addItem("uniform AQ")
        #self.aqModeSelection.addItem("auto variance")
        #self.aqModeSelection.addItem("auto variance with bias to dark scenes")
        #self.aqModeSelection.addItem("auto variance with edge information")

        #self.aqModeSelection.setCurrentIndex(self.config.aqmode)

        #self.aqModeSelection.currentIndexChanged.connect(self.onAQModeChange)

        #hlayout = QHBoxLayout()
        #label = QLabel("Adaptive Quantization Mode")
        #hlayout.addWidget(label)
        #hlayout.addStretch()
        #hlayout.addWidget(self.aqModeSelection)
        #label.setToolTip("--aq-mode (Mode for Adaptive Quantization)")
        #self.aqModeSelection.setToolTip("--aq-mode (Mode for Adaptive Quantization)")
        #rateCtlLayout.addLayout(hlayout)

        #self.hevcAqMotionCheckBox = QCheckBox()
        #self.hevcAqMotionCheckBox.setText("HEVC Adaptive Quantization")
        #self.hevcAqMotionCheckBox.setToolTip("--hevc-aq (Mode for HEVC Adaptive Quantization.)")
        #self.hevcAqMotionCheckBox.setDisabled(True)
        ##self.hevcAqMotionCheckBox.setChecked(bool(self.config.aqmotion))
        ##self.hevcAqMotionCheckBox.stateChanged.connect(self.onAQMotionChange)

        #hlayout = QHBoxLayout()
        #hlayout.addWidget(self.hevcAqMotionCheckBox)
        #hlayout.addStretch()
        #rateCtlLayout.addLayout(hlayout)


        #self.minKeyIntSpinBox = QSpinBox()
        #self.minKeyIntSpinBox.setMinimum(0)
        #self.minKeyIntSpinBox.setValue(self.config.minkeyint)
        #self.minKeyIntSpinBox.setMaximum(self.config.keyint - 1)
        #self.minKeyIntSpinBox.setSingleStep(1)
        #self.minKeyIntSpinBox.valueChanged.connect(self.onMinKeyIntChange)

        ##gridlayout.addWidget(QLabel("AQ Mode:"), 3, 0)
        ##gridlayout.addWidget(self.aqModeSelection, 3, 1)
        #hlayout = QHBoxLayout()
        #hlayout.addWidget(QLabel("Minimum Keyframe Interval"))
        #hlayout.addStretch()
        #hlayout.addWidget(self.minKeyIntSpinBox)
        #sliceDecisionLayout.addLayout(hlayout)

        #self.keyIntSpinBox = QSpinBox()
        #self.keyIntSpinBox.setMinimum(self.config.minkeyint + 1)
        #self.keyIntSpinBox.setMaximum(16384)
        #self.keyIntSpinBox.setValue(self.config.keyint)
        #self.keyIntSpinBox.setSingleStep(1)
        #self.keyIntSpinBox.valueChanged.connect(self.onKeyIntChange)

        ##gridlayout.addWidget(QLabel("AQ Mode:"), 3, 0)
        ##gridlayout.addWidget(self.aqModeSelection, 3, 1)
        #hlayout = QHBoxLayout()
        #hlayout.addWidget(QLabel("Maximum Keyframe Interval"))
        #hlayout.addStretch()
        #hlayout.addWidget(self.keyIntSpinBox)
        #sliceDecisionLayout.addLayout(hlayout)


        #self.aqStrengthSpinBox = QDoubleSpinBox()
        ##self.aqStrengthSpinBox.setMaximumWidth(128)
        #self.aqStrengthSpinBox.setMaximum(3)
        #self.aqStrengthSpinBox.setMinimum(0)
        #self.aqStrengthSpinBox.setDecimals(2)
        #self.aqStrengthSpinBox.setSingleStep(0.1)

        #self.aqStrengthSpinBox.setValue(self.config.aqstrength)

        #self.aqStrengthSpinBox.valueChanged.connect(self.onAQStrengthChange)

        ##gridlayout.addWidget(QLabel("AQ Strength:"), 4, 0)
        ##gridlayout.addWidget(self.aqStrengthSpinBox, 4, 1)
        #hlayout = QHBoxLayout()
        #label = QLabel("AQ Strength")
        #hlayout.addWidget(label)
        #hlayout.addStretch()
        #hlayout.addWidget(self.aqStrengthSpinBox)
        #label.setToolTip("--aq-strength")
        #self.aqStrengthSpinBox.setToolTip("--aq-strength")
        #rateCtlLayout.addLayout(hlayout)


        #self.aqMotionCheckBox = QCheckBox()
        #self.aqMotionCheckBox.setText("AQ Motion")
        #self.aqMotionCheckBox.setToolTip("--aq-motion (Block level QP adaptation based on the relative motion between the block and the frame.)")
        #self.aqMotionCheckBox.setChecked(bool(self.config.aqmotion))
        #self.aqMotionCheckBox.stateChanged.connect(self.onAQMotionChange)

        #hlayout = QHBoxLayout()
        #hlayout.addWidget(self.aqMotionCheckBox)
        #hlayout.addStretch()
        #rateCtlLayout.addLayout(hlayout)

        #self.qgSizeSelection = QComboBox()
        ##self.qgSizeSelection.setMaximumWidth(128)
        #self.qgSizeSelection.addItem("8")
        #self.qgSizeSelection.addItem("16")
        #self.qgSizeSelection.addItem("32")
        #self.qgSizeSelection.addItem("64")

        #if self.config.qgsize not in [8, 16, 32, 64]:
            #self.config.qgsize = 32
        #self.qgSizeSelection.setCurrentIndex([8, 16, 32, 64].index(self.config.qgsize))


        #self.qgSizeSelection.currentIndexChanged.connect(self.onQGSizeChange)

        ##gridlayout.addWidget(QLabel("Preset:"), 0, 0)
        ##gridlayout.addWidget(self.presetSelection, 0, 1)

        #hlayout = QHBoxLayout()
        #label = QLabel("QG Size")
        #label.setToolTip("--qg-size (Specifies the size of the quantization group (64, 32, 16, 8))")
        #hlayout.addWidget(label)
        #hlayout.addStretch()
        #self.qgSizeSelection.setToolTip("--qg-size (Specifies the size of the quantization group (64, 32, 16, 8))")
        #hlayout.addWidget(self.qgSizeSelection)
        #rateCtlLayout.addLayout(hlayout)

        #hlayout = QHBoxLayout()
        #hlayout.addWidget(QLabel("Level IDC"))
        #hlayout.addStretch()
        #self.levelidc = QComboBox(self.pltTab)
        #self.levelidc.setDisabled(True)
        #hlayout.addWidget(self.levelidc)
        #pltLayout.addLayout(hlayout)

        #self.hightier = QCheckBox("High Tier", self.pltTab)
        #self.hightier.setDisabled(True)
        #pltLayout.addWidget(self.hightier)

        #self.uhdbd = QCheckBox("Enable UHD Bluray compatibility support", self.pltTab)
        #self.uhdbd.setDisabled(True)
        #pltLayout.addWidget(self.uhdbd)

        #self.allownonconformance = QCheckBox("Allow Non-conformance", self.pltTab)
        #self.allownonconformance.setDisabled(True)
        #pltLayout.addWidget(self.allownonconformance)

        #pltLayout.addStretch()

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

    def onKeyIntChange(self, value):
        self.config.keyint = int(value)
        self.minKeyIntSpinBox.setMaximum(value - 1)
        self.isModified()

    def onMinKeyIntChange(self, value):
        self.config.minkeyint = int(value)
        self.keyIntSpinBox.setMinimum(value + 1)
        self.isModified()

    def onAQMotionChange(self, value):
        self.config.aqmotion = bool(value)
        self.isModified()

    def onAQModeChange(self, value):
        self.config.aqmode = value
        self.isModified()

    def onAQStrengthChange(self, value):
        self.config.aqstrength = value
        self.isModified()

    def onPresetChange(self, index):
        self.config.preset = self.presetSelection.itemText(index)
        self.isModified()

    def onProfileChange(self, index):
        self.config.profile = self.profileSelection.itemText(index)
        self.isModified()

    def onTuneChange(self, index):
        self.config.tune = self.tuneSelection.itemText(index) if index > 0 else None
        self.isModified()

    def onRateControlModeChange(self, index):
        if index == 0:
            self.config.bitrate = self.bitrateSpinBox.value()
            self.config.crf = None
            self.config.qp = None
            self.config.targetsize = None
            self.crfSpinBox.setHidden(True)
            self.qpSpinBox.setHidden(True)
            self.targetSizeSpinBox.setHidden(True)
            self.bitrateSpinBox.setHidden(False)
        elif index == 1:
            self.config.bitrate = None
            self.config.crf = self.crfSpinBox.value()
            self.config.qp = None
            self.config.targetsize = None
            self.bitrateSpinBox.setHidden(True)
            self.qpSpinBox.setHidden(True)
            self.targetSizeSpinBox.setHidden(True)
            self.crfSpinBox.setHidden(False)
        elif index == 2:
            self.config.bitrate = None
            self.config.crf = None
            self.config.qp = self.qpSpinBox.value()
            self.config.targetsize = None
            self.bitrateSpinBox.setHidden(True)
            self.crfSpinBox.setHidden(True)
            self.targetSizeSpinBox.setHidden(True)
            self.qpSpinBox.setHidden(False)
        elif index == 3:
            self.config.bitrate = None
            self.config.crf = None
            self.config.qp = None
            self.config.targetsize = self.targetSizeSpinBox.value()*1024**2
            self.bitrateSpinBox.setHidden(True)
            self.crfSpinBox.setHidden(True)
            self.qpSpinBox.setHidden(True)
            self.targetSizeSpinBox.setHidden(False)
        self.isModified()

    def onQGSizeChange(self, value):
        self.config.qgsize = [8, 16, 32, 64][value]
        self.isModified()

    def setBitrate(self, value):
        self.config.bitrate = value
        self.isModified()

    def setTargetSize(self, value):
        self.config.targetsize = value*1024**2
        self.isModified()

    def setCRF(self, value):
        self.config.crf = value
        self.isModified()

    def setQP(self, value):
        self.config.qp = value
        self.isModified()

    def setFrameRate(self, fpstext):
        if regex.match(r"^\d+/\d+$", fpstext):
            self.config.fps = QQ(fpstext)
        elif regex.match(r"^\d+$", fpstext):
            self.config.fps = int(fpstext)
        elif regex.match(r"^\d+\.\d?|\.\d+$", fpstext):
            self.config.fps = float(fpstext)
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


#from PyQt5.QtCore import QRegExp
#from PyQt5.QtGui import QRegExpValidator
#from PyQt5.QtWidgets import QAbstractSpinBox

#class FileSizeSpinBox(QAbstractSpinBox):
    #def __init__(self, *args, **kwargs):
        #super().__init__(*args, **kwargs)
        #self._regex = QRegExp(r"^(\d+(?:\.\d+)?|\.\d+)(B|KB|MB|GB)?$")
        #self._validator = QRegExpValidator(self._regex)
        #self.lineEdit().setValidator(self._validator)

    #def interpretText(self):
        #text = self.lineEdit().text()
        #print(self._regex.capturedTexts())
        #val = super().interpretText()
        #print(val)
        #return val
