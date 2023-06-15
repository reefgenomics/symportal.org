import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))


class Config(object):
    # Load environment variables from .env file
    load_dotenv()

    SECRET_KEY = os.environ.get(
        'SECRET_KEY') or 'there_was_a_lady_from_nantucket'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
                              'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Log file configuration
    LOG_FILE = os.environ.get('LOG_FILE') or 'flask-app.log'
    LOG_LEVEL = os.environ.get('LOG_LEVEL') or 'DEBUG'
