from app import app
from app.models import db
import os

if __name__ == '__main__':
    app.debug = True
    app.secret_key = os.urandom(12)
    db.create_all()
    app.run()
