"""
Flask-MoSession
-----------
Flask-Session provides mongodb based server side session management system for Flask.

"""
from setuptools import setup

setup(
    name='Flask-MoSession',
    version='0.2',
    url='',
    license='BSD',
    author='Mehdi Bayazee, Mostafa Rokooie',
    author_email='bayazee@gmail.com, mostafa.rokooie@gmail.com',
    description='mongodb based server side session management system for Flask',
    long_description=__doc__,
    py_modules=['flask_mosession'],
    zip_safe=False,
    platforms='any',
    install_requires=[
        'Flask>=0.9',
        'pycrypto>2.4.1'
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
)
