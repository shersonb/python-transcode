from distutils.core import setup

setup(
    name='transcode',
    version='0.0.1',
    description='Transcoder for Python',
    author='Brian Sherson',
    author_email='caretaker82@gmail.com',
    url='https://github.com/shersonb/python-transcode',
    packages=[
        'transcode',
        'transcode.config',
        'transcode.config.ebml',
        'transcode.filters',
        'transcode.filters.audio',
        'transcode.filters.audio.chanmix',
        'transcode.filters.video',
        'transcode.filters.video.cropandresize',
        'transcode.filters.video.dropframes',
        'transcode.filters.video.fps',
        'transcode.filters.video.hsladjust',
        'transcode.filters.video.keyframes',
        'transcode.filters.video.levels',
        'transcode.filters.video.pullup',
        'transcode.filters.video.scenes',
        'transcode.filters.concatenate',
        'transcode.filters.crossfade',
        'transcode.filters.slice',
        'transcode.containers',
        'transcode.containers.matroska',
        'transcode.containers.matroska.pyqtgui',
        'transcode.containers.matroska.pyqtgui.chapters',
        'transcode.encoders',
        'transcode.encoders.audio',
        'transcode.encoders.video',
        'transcode.encoders.libx265',
        'transcode.encoders.ac3',
        'transcode.encoders.libfdk_aac',
        'transcode.pyqtgui',
    ],
    scripts=[
        'bin/qtranscode',
        'bin/qtranscode-config'
    ],
    install_requires=[
        'ebml', 'matroska', 'titlecase', 'ass', 'av', 'ciqueue',
        'numpy', 'scipy', 'lzma', 'Pillow', 'xml', 'json',
        'regex', 'itertools', 'more_itertools', 'scenedetect'
    ],
    license="MIT"
)
