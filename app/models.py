from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime
from app import app
from flask_mail import Mail,Message
import pymysql 
pymysql.install_as_MySQLdb()

#SqlAlchemy Database Configuration With Mysql
app.config['MAIL_SERVER']='smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = 'upsclae.io@gmail.com'
app.config['MAIL_PASSWORD'] = 'upscalee'
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:''@localhost/upscale'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


db = SQLAlchemy(app)
migrate = Migrate(app, db)

class User(db.Model):
    """ Create user table"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True)
    password = db.Column(db.String(80))
    email = db.Column(db.String(80))
    name = db.Column(db.String(80))
    activated = db.Column(db.Integer)
    dateTime = db.Column(db.String(80))
    isAdmin = db.Column(db.String(40))

    def __init__(self, username, password, email, name,activated,dateTime,isAdmin):
        self.username = username
        self.password = password
        self.email = email
        self.name = name
        self.activated = activated
        self.dateTime = dateTime
        self.isAdmin = isAdmin

class UploadImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    data = db.Column(db.LargeBinary, nullable=False)#Actual data, needed for Download
    rendered_data = db.Column(db.Text, nullable=False)#Data to render the pic in browser
    pic_date = db.Column(db.DateTime, nullable=False,default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    model_name = db.Column(db.String(40))

    def __repr__(self):
        return f'Pic Name: {self.name} Data: {self.data} created on: {self.pic_date}'

class Discuss(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.String(350))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    upload_date = db.Column(db.String(80))

    def __init__(self,body,user_id,upload_date):
        self.body = body
        self.user_id = user_id
        self.upload_date = upload_date

class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    body = db.Column(db.String(1000))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    upload_date = db.Column(db.String(80))
    img_name =  db.Column(db.String(100))
    model = db.Column(db.String(80))

    def __init__(self,title,body,user_id,upload_date,img_name,model):
        self.title = title
        self.body = body
        self.user_id = user_id
        self.upload_date = upload_date
        self.img_name = img_name
        self.model = model

class ContactUs(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    email = db.Column(db.String(250), nullable=False)
    subject = db.Column(db.String(300), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    time = db.Column(db.String(80))

    def __init__(self,name, email,subject,message,time):
        self.name = name
        self.email = email
        self.subject = subject
        self.message = message
        self.time = time