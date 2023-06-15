from flask import Flask
from config import Config, basedir
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
import os

# Configure logging
import logging
from logging.handlers import RotatingFileHandler


db_user = os.environ.get('POSTGRES_USER')
db_password = os.environ.get('POSTGRES_PASSWORD')
db_host = os.environ.get('SYMPORTAL_DATABASE_CONTAINER')  # Use the service name as the hostname when accessing containers within the same network
db_port = '5432'
db_name = os.environ.get('POSTGRES_DB')

app = Flask(__name__)
app.config.from_object(Config)

app.config['SQLALCHEMY_BINDS'] = {
   'symportal_database': f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
}

db = SQLAlchemy(app)
migrate = Migrate(app,db)
login = LoginManager(app)
login.login_view = 'login'

# Configure logging
handler = RotatingFileHandler('flask_app.log', maxBytes=100000, backupCount=5)
handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
app.logger.addHandler(handler)

from sp_app import routes, models
