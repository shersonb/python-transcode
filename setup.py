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
        'transcode.containers',
        'transcode.containers.matroska',
        'transcode.encoders',
        'transcode.encoders.audio',
        'transcode.encoders.video',
        'transcode.pyqtgui',
        ],
    scripts=['bin/qtranscode'],
    install_requires=[
            'ebml', 'matroska'
        ],
    license="MIT"
)
