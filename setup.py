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
        'transcode.filters.video',
        'transcode.filters.video.fps',
        'transcode.filters.video.levels',
        'transcode.filters.video.cropandresize',
        'transcode.filters.concatenate',
        'transcode.containers',
        'transcode.containers.matroska',
        'transcode.containers.matroska.pyqtgui',
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
        'ebml', 'matroska', 'titlecase', 'ass', 'av'
    ],
    license="MIT"
)
