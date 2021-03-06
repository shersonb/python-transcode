#!/usr/bin/python
from fractions import Fraction as QQ
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QComboBox,
                             QSpinBox, QDoubleSpinBox, QLabel, QPushButton,
                             QCheckBox, QLineEdit, QWidget, QTabWidget)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import pyqtSignal
from . import x265colonrationalparams, x265slashrationalparams


class Choices(QWidget):
    def __init__(self, encoder, optname, attrname, choices, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
    def __init__(self, encoder, optname, attrname, minval, maxval,
                 step, *args, **kwargs):
        super().__init__(*args, **kwargs)
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


class StrOption(QWidget):
    def __init__(self, encoder, optname, attrname, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.encoder = encoder
        self.optname = optname
        self.attrname = attrname

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.label = QLabel(optname, self)
        layout.addWidget(self.label)

        layout.addStretch()

        self.textBox = QLineEdit(self)
        layout.addWidget(self.textBox)

        currentvalue = getattr(encoder, attrname)

        if currentvalue is not None:
            self.textBox.setText(currentvalue)

        else:
            self.textBox.setText("")

        self.textBox.textChanged.connect(self.textChanged)

    def textChanged(self, value):
        if value:
            setattr(self.encoder, self.attrname, value)

        else:
            setattr(self.encoder, self.attrname, None)


class FloatOption(QWidget):
    def __init__(self, encoder, optname, attrname, minval, maxval,
                 step, decimals, *args, **kwargs):
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
        super().__init__(*args, **kwargs)
        self.encoder = encoder
        self.setText(optname)
        self.attrname = attrname
        self.setTristate(kwargs.get("tristate", True))

        currentvalue = getattr(encoder, attrname)

        if currentvalue is not None:
            self.setCheckState(2 if currentvalue else 0)

        elif self.isTristate():
            self.setCheckState(1)

        self.stateChanged.connect(self.setOpt)

    def setOpt(self, state):
        if state == 0 and self.isTristate():
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
        self.preset = Choices(
            encoder, "Preset", "preset",
            ["ultrafast", "superfast", "veryfast", "faster", "fast",
             "medium", "slow", "slower", "veryslow", "placebo"],
            self)
        self.preset.selection.currentIndexChanged.connect(
            self.optionchanged.emit)
        self.preset.setToolTip("""
            <b>--preset, -p &lt;integer|string&gt;</b>
            <p>Sets parameters to preselected values, trading off compression
            efficiency against encoding speed. These parameters are applied
            before all other input parameters are applied, and so you can
            override any parameters that these values control.</p>
            """)
        layout.addWidget(self.preset)

        self.tune = Choices(
            encoder, "Tune", "tune",
            ["None", "psnr", "ssim", "grain", "zerolatency",
             "fast-decode", "animation"],
            self)
        self.tune.selection.currentIndexChanged.connect(
            self.optionchanged.emit)
        self.tune.setToolTip("""
            <b>--tune, -t &lt;string&gt;</b>
            <p>Tune the settings for a particular type of source or situation.
            The changes will be applied after --preset but before all other
            parameters. Default none.</p>
            """)
        layout.addWidget(self.tune)

        # TODO: Insert --asm

        self.framethreads = IntOption(
            encoder, "Frame Threads", "frame-threads", -1, 16, 1, self)
        self.framethreads.spinbox.valueChanged.connect(
            self.optionchanged.emit)
        self.framethreads.setToolTip("""
            <b>--frame-threads, -F &lt;integer&gt;</b>
            <p>Number of concurrently encoded frames. Using a single frame
            thread gives a slight improvement in compression, since the entire
            reference frames are always available for motion compensation, but
            it has severe performance implications. Default is an autodetected
            count based on the number of CPU cores and whether WPP is enabled
            or not.</p>
            <p>Over-allocation of frame threads will not improve performance,
            it will generally just increase memory use.</p>
            <p>Values: any value between 0 and 16. Default is 0,
            auto-detect.</p>
            """)
        layout.addWidget(self.framethreads)

        # TODO: Insert --pools

        self.numapools = StrOption(encoder, "Numa Pools", "numa-pools", self)
        self.numapools.textBox.textChanged.connect(self.optionchanged.emit)
        layout.addWidget(self.numapools)

        self.slices = IntOption(encoder, "Slices", "slices", 0, 16, 1, self)
        self.slices.spinbox.valueChanged.connect(self.optionchanged.emit)
        self.slices.setToolTip("""
            <b>--slices &lt;integer&gt;</b>
            <p>Encode each incoming frame as multiple parallel slices that may
            be decoded independently. Support available only for rectangular
            slices that cover the entire width of the image.</p>
            <p>Recommended for improving encoder performance only if
            frame-parallelism and WPP are unable to maximize utilization on
            given hardware.</p>
            <p>Default: 1 slice per frame. Experimental feature.</p>
            """)
        layout.addWidget(self.slices)

        self.wpp = BoolOption(
            encoder, "Wavefront Parallel Processing", "wpp", self)
        self.wpp.stateChanged.connect(self.optionchanged.emit)
        layout.addWidget(self.wpp)

        self.pmode = BoolOption(
            encoder, "Parallel Mode Decision", "pmode", self)
        self.pmode.stateChanged.connect(self.optionchanged.emit)
        layout.addWidget(self.pmode)

        self.pme = BoolOption(
            encoder, "Parallel Motion Estimation", "pme", self)
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
        self.rd.setToolTip("""
            <b>--rd &lt;1..6&gt;</b>
            <p>Level of RDO in mode decision. The higher the value, the more
            exhaustive the analysis and the more rate distortion optimization
            is used. The lower the value the faster the encode, the higher the
            value the smaller the bitstream (in general). Default 3.</p>
            """)
        layout.addWidget(self.rd)

        self.ctu = Choices(encoder, "Maximum CU Size",
                           "ctu", [16, 32, 64], self)
        self.ctu.selection.currentIndexChanged.connect(
            self.optionchanged.emit)
        self.ctu.setToolTip("""
            <b>--ctu, -s &lt;64|32|16&gt;</b>
            <p>Maximum CU size (width and height). The larger the maximum CU
            size, the more efficiently x265 can encode flat areas of the
            picture, giving large reductions in bitrate. However this comes at
            a loss of parallelism with fewer rows of CUs that can be encoded
            in parallel, and less frame parallelism as well. Because of this
            the faster presets use a CU size of 32. Default: 64</p>
            """)
        layout.addWidget(self.ctu)

        self.mincusize = Choices(
            encoder, "Minimum CU Size", "min-cu-size", [8, 16, 32], self)
        self.mincusize.selection.currentIndexChanged.connect(
            self.optionchanged.emit)
        self.mincusize.setToolTip("""
            <b>--min-cu-size &lt;32|16|8&gt;</b>
            <p>Minimum CU size (width and height). By using 16 or 32 the
            encoder will not analyze the cost of CUs below that minimum
            threshold, saving considerable amounts of compute with a
            predictable increase in bitrate. This setting has a large effect
            on performance on the faster presets.</p>
            <p>Default: 8 (minimum 8x8 CU for HEVC, best compression
            efficiency)</p>
            """)
        layout.addWidget(self.mincusize)

        self.limitrefs = IntOption(
            encoder, "Limit References", "limit-refs", -1, 3, 1, self)
        self.limitrefs.spinbox.valueChanged.connect(self.optionchanged.emit)
        self.limitrefs.setToolTip("""
            <b>--limit-refs &lt;0|1|2|3&gt;</b>
            <p>When set to X265_REF_LIMIT_DEPTH (1) x265 will limit the
            references analyzed at the current depth based on the references
            used to code the 4 sub-blocks at the next depth. For example, a
            16x16 CU will only use the references used to code its four 8x8
            CUs.</p>
            <p>When set to X265_REF_LIMIT_CU (2), the rectangular and
            asymmetrical partitions will only use references selected by the
            2Nx2N motion search (including at the lowest depth which is
            otherwise unaffected by the depth limit).</p>
            <p>When set to 3 (X265_REF_LIMIT_DEPTH && X265_REF_LIMIT_CU), the
            2Nx2N motion search at each depth will only use references from
            the split CUs and the rect/amp motion searches at that depth will
            only use the reference(s) selected by 2Nx2N.</p>
            <p>For all non-zero values of limit-refs, the current depth will
            evaluate intra mode (in inter slices), only if intra mode was
            chosen as the best mode for atleast one of the 4 sub-blocks.</p>
            <p>You can often increase the number of references you are using
            (within your decoder level limits) if you enable one or both of
            these flags.</p>
            <p>Default 3.</p>
            """)
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
        self.opengop.setToolTip("""
            <b>--open-gop, --no-open-gop</b>
            <p>Enable open GOP, allow I-slices to be non-IDR. Default
            enabled.</p>
            """)
        layout.addWidget(self.opengop)

        self.keyint = IntOption(
            encoder, "Maximum Keyframe Interval", "keyint", 0, 1440, 1, self)
        self.keyint.spinbox.valueChanged.connect(self.optionchanged.emit)
        self.keyint.setToolTip("""
            <b>--keyint, -I &lt;integer&gt;</b>
            <p>Max intra period in frames. A special case of infinite-gop
            (single keyframe at the beginning of the stream) can be triggered
            with argument -1. Use 1 to force all-intra. When intra-refresh is
            enabled it specifies the interval between which refresh sweeps
            happen. Default 250.</p>
            """)
        layout.addWidget(self.keyint)

        self.minkeyint = IntOption(
            encoder, "Minimum Keyframe Interval", "min-keyint",
            0, 1440, 1, self)
        self.minkeyint.spinbox.valueChanged.connect(self.optionchanged.emit)
        self.minkeyint.setToolTip("""
            <b>--min-keyint, -i &lt;integer&gt</b>
            <p>Minimum GOP size. Scenecuts beyond this interval are coded as
            IDR and start a new keyframe, while scenecuts closer together are
            coded as I or P. For fixed keyframe interval, set value to be
            equal to keyint.</p>
            <p>Range of values: >=0 (0: auto).</p>
            """)
        layout.addWidget(self.minkeyint)

        self.scenecut = IntOption(
            encoder, "Scenecut threshold", "scenecut", -1, 100, 1, self)
        self.scenecut.spinbox.valueChanged.connect(self.optionchanged.emit)
        self.scenecut.setToolTip("""
            <b>--scenecut <integer>, --no-scenecut</b>
            <p>How aggressively I-frames need to be inserted. The higher the
            threshold value, the more aggressive the I-frame placement.
            --scenecut 0 or --no-scenecut disables adaptive I frame placement.
            Default 40.</p>
            """)
        layout.addWidget(self.scenecut)

        self.scenecutbias = FloatOption(
            encoder, "Scenecut Bias", "scenecut-bias", -0.1, 100, 1, 1, self)
        self.scenecutbias.spinbox.valueChanged.connect(
            self.optionchanged.emit)
        self.scenecutbias.spinbox.setSuffix("%")
        self.scenecutbias.setToolTip("""
            <b>--scenecut-bias &lt;0..100.0&gt;</b>
            <p>This value represents the percentage difference between the
            inter cost and intra cost of a frame used in scenecut detection.
            For example, a value of 5 indicates, if the inter cost of a frame
            is greater than or equal to 95 percent of the intra cost of the
            frame, then detect this frame as scenecut. Values between 5 and 15
            are recommended. Default 5.</p>
            """)
        layout.addWidget(self.scenecutbias)

        self.rclookahead = IntOption(
            encoder, "RC Lookahead", "rc-lookahead", -1, 250, 1, self)
        self.rclookahead.spinbox.valueChanged.connect(self.optionchanged.emit)
        self.rclookahead.setToolTip("""
            <b>--rc-lookahead &lt;integer&gt;</b>
            <p>Number of frames for slice-type decision lookahead (a key
            determining factor for encoder latency). The longer the lookahead
            buffer the more accurate scenecut decisions will be, and the more
            effective cuTree will be at improving adaptive quant.
            Having a lookahead larger than the max keyframe interval is not
            helpful. Default 20.</p>
            <p>Range of values: Between the maximum consecutive bframe count
            (--bframes) and 250.</p>
            """)
        layout.addWidget(self.rclookahead)

        self.goplookahead = IntOption(
            encoder, "GOP Lookahead", "gop-lookahead", -1, 250, 1, self)
        self.goplookahead.spinbox.valueChanged.connect(
            self.optionchanged.emit)
        self.goplookahead.setToolTip("""
            <b>--gop-lookahead &lt;integer&gt;</n>
            <p>Number of frames for GOP boundary decision lookahead. If a
            scenecut frame is found within this from the gop boundary set by
            –keyint, the GOP will be extented until such a point, otherwise
            the GOP will be terminated as set by –keyint. Default 0.</p>
            <p>Range of values: Between 0 and (–rc-lookahead - mini-GOP
            length).</p>
            <p>It is recommended to have –gop-lookahaed less than –min-keyint
            as scenecuts beyond –min-keyint are already being coded as
            keyframes.
            """)
        layout.addWidget(self.goplookahead)

        self.lookaheadslices = IntOption(
            encoder, "Lookahead Slices", "lookahead-slices", -1, 16, 1, self)
        self.lookaheadslices.spinbox.valueChanged.connect(
            self.optionchanged.emit)
        self.lookaheadslices.setToolTip("""
            <b>--lookahead-slices &lt;0..16&gt;</b>
            <p>Use multiple worker threads to measure the estimated cost of
            each frame within the lookahead. The frame is divided into the
            specified number of slices, and one-thread is launched per slice.
            When --b-adapt is 2, most frame cost estimates will be performed
            in batch mode (many cost estimates at the same time) and
            lookahead-slices is ignored for batched estimates; it may still be
            used for single cost estimations. The higher this parameter, the
            less accurate the frame costs will be (since context is lost
            across slice boundaries) which will result in less accurate
            B-frame and scene-cut decisions. The effect on performance can be
            significant especially on systems with many threads.</p>
            <p>The encoder may internally lower the number of slices or
            disable slicing to ensure each slice codes at least 10 16x16 rows
            of lowres blocks to minimize the impact on quality. For example,
            for 720p and 1080p videos, the number of slices is capped to 4 and
            6, respectively. For resolutions lesser than 720p, slicing is
            auto-disabled.</p>
            <p>If slices are used in lookahead, they are logged in the list of
            tools as lslices.</p>
            <p>Values: 0 - disabled. 1 is the same as 0. Max 16. Default: 8
            for ultrafast, superfast, faster, fast, medium</p>
            <p>4 for slow, slower disabled for veryslow, slower</p>
            """)
        layout.addWidget(self.lookaheadslices)

        self.badapt = Choices(
            encoder, "B-frame adapt", "b-adapt",
            [("None", 0), ("Fast", 1), ("Full (Trellis)", 2)], self)
        self.badapt.selection.currentIndexChanged.connect(
            self.optionchanged.emit)
        self.badapt.setToolTip("""
            <b>--b-adapt &lt;integer&gt</b>
            <p>Set the level of effort in determining B frame placement.</p>
            <p>With b-adapt 0, the GOP structure is fixed based on the values
            of --keyint and --bframes.</p>
            <p>With b-adapt 1 a light lookahead is used to choose B frame
            placement.</p>
            <p>With b-adapt 2 (trellis) a viterbi B path selection is
            performed.</p>
            <p>Values: 0:none; 1:fast; 2:full(trellis) default</p>
            """)
        layout.addWidget(self.badapt)

        self.bframes = IntOption(
            encoder, "Maximum consecutive B frames", "bframes",
            -1, 16, 1, self)
        self.bframes.spinbox.valueChanged.connect(self.optionchanged.emit)
        self.bframes.setToolTip("""
            <b>--bframes, -b &lt;0..16&gt</b>
            <p>Maximum number of consecutive b-frames. Use <span
            class="pre">--bframes</span> 0 to force all P/I low-latency
            encodes. Default 4. This parameter has a quadratic effect on the
            amount of memory allocated and the amount of work performed by the
            full trellis version of <span class="pre">--b-adapt</span>
            lookahead.</p>
            """)
        layout.addWidget(self.bframes)

        """
        TODO:
        --lookahead-threads
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

        self.rateControlSelection.currentIndexChanged.connect(
            self.onRateControlModeChange)
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

        self.aqmotion = BoolOption(encoder, "AQ Motion", "aq-motion", self)
        self.aqmotion.stateChanged.connect(self.optionchanged.emit)
        self.aqmotion.setToolTip("""
            <b>--aq-motion, --no-aq-motion</b>
            <p>Adjust the AQ offsets based on the relative motion of each
            block with respect to the motion of the frame. The more the
            relative motion of the block, the more quantization is used.</p>
            <p>Default disabled. <b>Experimental Feature.</b></p>
            """)
        layout.addWidget(self.aqmotion)

        self.aqmode = Choices(
            encoder, "AQ Mode", "aq-mode",
            [("Disabled", 0), ("AQ Enabled", 1),
             ("AQ enabled with auto-variance", 2),
             ("AQ enabled with auto-variance and bias to dark scenes", 3),
             ("AQ enabled with auto-variance and edge information", 4)],
            self)
        self.aqmode.selection.currentIndexChanged.connect(
            self.optionchanged.emit)
        self.aqmode.setToolTip("""
            <b>--aq-mode &lt;0|1|2|3|4&gt;</b>
            <p>Adaptive Quantization operating mode. Raise or lower per-block
            quantization based on complexity analysis of the source image. The
            more complex the block, the more quantization is used. These
            offsets the tendency of the encoder to spend too many bits on
            complex areas and not enough in flat areas.</p>
            """)
        layout.addWidget(self.aqmode)

        self.aqstrength = FloatOption(
            encoder, "AQ Strength", "aq-strength", 0, 3, 1, 2, self)
        self.aqstrength.spinbox.valueChanged.connect(self.optionchanged.emit)
        self.aqstrength.setToolTip("""
            <b>--aq-strength &lt;float&gt;</b>
            <p>Adjust the strength of the adaptive quantization offsets.
            Setting <span class="pre">--aq-strength</span> to 0 disables AQ.
            At aq-modes 2 and 3, high aq-strengths will lead to high QP
            offsets resulting in a large difference in achieved bitrates.</p>
            <p>Default 1.0. Range of values: 0.0 to 3.0</p>
            """)
        layout.addWidget(self.aqstrength)

        self.qgsize = Choices(
            encoder, "QG Size", "qg-size",
            [("8", 8), ("16", 16), ("32", 32), ("64", 64)], self)
        self.qgsize.selection.currentIndexChanged.connect(
            self.optionchanged.emit)
        self.qgsize.setToolTip("""
            <b>--qg-size &lt;64|32|16|8&gt;</b>
            <p>Enable adaptive quantization for sub-CTUs. This parameter
            specifies the minimum CU size at which QP can be adjusted, ie.
            Quantization Group size. Allowed range of values are 64, 32, 16, 8
            provided this falls within the inclusive range [maxCUSize,
            minCUSize].</p>
            <p>Default: same as maxCUSize</p>
            """)
        layout.addWidget(self.qgsize)

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

        --aq-motion
        --hevc-aq
        --qp-adaptation-range
        #--qg-size
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


class ProfileLevelTierTab(QWidget):
    optionchanged = pyqtSignal()

    def __init__(self, encoder, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.encoder = encoder

        layout = QVBoxLayout()
        layout.setSpacing(4)
        self.setLayout(layout)

        self.levelidc = Choices(
            encoder, "Level IDC", "level-idc",
            [("1", 1), ("2", 2), ("2.1", 2.1), ("3", 3), ("3.1", 3.1),
             ("4", 4), ("4.1", 4.1), ("5", 5), ("5.1", 5.1),
             ("6", 6), ("6.1", 6.1), ("6.2", 6.2), ("8.5", 8.5)], self)
        self.levelidc.selection.currentIndexChanged.connect(
            self.optionchanged.emit)
        self.levelidc.setToolTip("""
            <b>--level-idc &lt;integer|float&gt;</b>
            <p>Minimum decoder requirement level. Defaults to 0, which implies
            auto-detection by the encoder. If specified, the encoder will
            attempt to bring the encode specifications within that specified
            level. If the encoder is unable to reach the level it issues a
            warning and aborts the encode. If the requested requirement level
            is higher than the actual level, the actual requirement level is
            signaled.</p>
            <p>Beware, specifying a decoder level will force the encoder to
            enable VBV for constant rate factor encodes, which may introduce
            non-determinism.</p>
            <p>The value is specified as a float or as an integer with the
            level times 10, for example level 5.1 is specified as “5.1” or
            “51”, and level 5.0 is specified as “5.0” or “50”.
            """)
        layout.addWidget(self.levelidc)

        self.hightier = BoolOption(encoder, "High-tier", "high-tier", self)
        self.hightier.stateChanged.connect(self.optionchanged.emit)
        self.hightier.setToolTip("""
            <b>--high-tier, --no-high-tier</b>
            <p>If --level-idc has been specified, –high-tier allows the
            support of high tier at that level. The encoder will first attempt
            to encode at the specified level, main tier first, turning on high
            tier only if necessary and available at that level. If your
            requested level does not support a High tier, high tier will not
            be supported. If –no-high-tier has been specified, then the
            encoder will attempt to encode only at the main tier.</p>
            <p>Default: enabled</p>
            """)
        layout.addWidget(self.hightier)

        self.refs = IntOption(
            encoder, "Max L0 References", "ref", 0, 16, 1, self)
        self.refs.spinbox.valueChanged.connect(self.optionchanged.emit)
        self.refs.setToolTip("""
            <b>--ref &lt;1..16&gt;</b>
            <p>Max number of L0 references to be allowed. This number has a
            linear multiplier effect on the amount of work performed in
            motion search but will generally have a beneficial effect on
            compression and distortion.</p>
            <p>Note that x265 allows up to 16 L0 references but the HEVC
            specification only allows a maximum of 8 total reference
            frames. So if you have B frames enabled only 7 L0 refs are
            valid and if you have --b-pyramid enabled (which is enabled by
            default in all presets), then only 6 L0 refs are the maximum
            allowed by the HEVC specification. If x265 detects that the
            total reference count is greater than 8, it will issue a
            warning that the resulting stream is non-compliant and it
            signals the stream as profile NONE and level NONE and will
            abort the encode unless --allow-non-conformance it specified.
            Compliant HEVC decoders may refuse to decode such streams.</p>
            <p>Default 3</p>
            """)
        layout.addWidget(self.refs)

        self.nonconformance = BoolOption(
            encoder, "Allow non-conformance", "allow-non-conformance", self)
        self.nonconformance.stateChanged.connect(self.optionchanged.emit)
        self.nonconformance.setToolTip("""
            <b>--allow-non-conformance, --no-allow-non-conformance</b>
            <p>Allow libx265 to generate a bitstream with profile and level
            NONE. By default, it will abort any encode which does not meet
            strict level compliance. The two most likely causes for non-
            conformance are <span class="pre">--ctu</span> being too small,
            <span class="pre">--ref</span> being too high, or the bitrate or
            resolution being out of specification.</p>
            <p>Default: disabled</p>
            """)
        layout.addWidget(self.nonconformance)

        self.uhdbd = BoolOption(
            encoder, "Enable Ultra HD Blu-ray format support", "uhd-bd",
            self, tristate=False)
        self.uhdbd.stateChanged.connect(self.optionchanged.emit)
        self.uhdbd.setToolTip("""
            <b>--uhd-bd</b>
            <p>Enable Ultra HD Blu-ray format support. If specified with
            incompatible encoding options, the encoder will attempt to
            modify/set the right encode specifications. If the encoder is
            unable to do so, this option will be turned OFF. Highly
            experimental.</p>
            <p>Default: disabled</p>
            """)
        layout.addWidget(self.uhdbd)

        layout.addStretch()


class x265ConfigDlg(QDialog):
    settingsApplied = pyqtSignal()

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

        self.leveltier = ProfileLevelTierTab(encoder, self.tabs)
        self.leveltier.optionchanged.connect(self.isModified)
        self.tabs.addTab(self.leveltier, "Level/Tier")

        self.modedec = ModeDecisionAnalysisTab(encoder, self.tabs)
        self.modedec.optionchanged.connect(self.isModified)
        self.tabs.addTab(self.modedec, "Mode Decision/Analysis")

        self.sliceDecision = SliceDecisionTab(encoder, self.tabs)
        self.sliceDecision.optionchanged.connect(self.isModified)
        self.tabs.addTab(self.sliceDecision, "Slice Decision")

        self.optionsLabel = QLabel("libx265 options: ", self)
        self.optionsLabel.setWordWrap(True)
        layout.addWidget(self.optionsLabel)

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
        self.setStyleSheet(
            self.styleSheet() + """
            span.pre {
                box-sizing: border-box;
                font-weight: 700;
                font-family: monospace;
                }
            """)

    def applyAndClose(self):
        self.settingsApplied.emit()
        self.done(1)
        self.close()

    def updateOptionLabel(self):
        opts = []

        if self.encoder.crf is not None:
            opts.append(f"--crf {self.encoder.crf:.2f}")

        for key, value in self.encoder.x265params.items():
            if value is True:
                opts.append(f"--{key}")

            elif value is False:
                opts.append(f"--no-{key}")

            elif isinstance(value, str):
                opts.append(f"--{key} {value}")

            elif isinstance(value, QQ):
                if key in x265colonrationalparams:
                    opts.append(f"--{key} {value.numerator}"
                                f"\\:{value.denominator}")

                if key in x265slashrationalparams:
                    opts.append(f"--{key} {value.numerator}"
                                f"/{value.denominator}")

            elif value is not None:
                opts.append(f"--{key} {value}")

        self.optionsLabel.setText(f"libx265 options: {' '.join(opts)}")

    def isModified(self, flag=True):
        self.updateOptionLabel()
        self.okayBtn.setEnabled(flag)

        if flag:
            self.cancelBtn.setText("&Cancel")

        else:
            self.cancelBtn.setText("&Close")
