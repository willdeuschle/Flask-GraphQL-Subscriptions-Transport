from setuptools import setup

required_packages = [
    'flask_socketio',
    'flask',
    'json',
]

setup(name='flask_graphql_subscriptions_transport',
      version='0.1.0',
      description='Adds subscription transport layer for Flask applications using GraphQL',
      url='https://github.com/willdeuschle/Flask-GraphQL-Subscriptions-Transport',
      author='Will Deuschle',
      author_email='wjdeuschle@gmail.com',
      license='MIT',
      packages=['flask_graphql_subscriptions_transport'],
      install_requires=required_packages,
      tests_require=['pytest'],
      zip_safe=False)
