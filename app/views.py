from flask import Flask, render_template, redirect, url_for, request, session, abort, flash, send_file,send_from_directory
from flask_mail import Mail,Message
from app import app
from app import models
from app.models import User,db,UploadImage,Discuss,Article,ContactUs
from itsdangerous import URLSafeTimedSerializer, SignatureExpired
from authlib.integrations.flask_client import OAuth
import random
import os
import string
import datetime
from base64 import b64encode
import base64
from io import BytesIO
from werkzeug.utils import secure_filename
from pathlib import Path
import PIL 
from PIL import Image 

# from app import upscale


postd = Mail(app)

s = URLSafeTimedSerializer('Thisisasecret!')

ALLOWED_EXTENSIONS = {'jpg'}

oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id='622079679280-0vljd7h4mmkojl7g68sb1f8ivjcdp0sk.apps.googleusercontent.com',
    client_secret='gH9s213oW3BzzL8M_WkcMekI',
    access_token_url='https://accounts.google.com/o/oauth2/token',
    access_token_params=None,
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    authorize_params=None,
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    userinfo_endpoint='https://openidconnect.googleapis.com/v1/userinfo',  # This is only needed if using openId to fetch user info
    client_kwargs={'scope': 'openid email profile'},
)

@app.route('/', methods=['GET', 'POST'])
def index():   
    """ Session control"""
    if not session.get('logged_in'):
        if request.method == 'POST':
            name = request.form["name"]
            email = request.form["email"]
            subject = request.form["subject"]
            message = request.form["message"]
            time = datetime.datetime.now()

            if name == "" or email == "" or subject == "" or message == "":
                flash("Fields must not be left blank", "warning")
            else:
                data = ContactUs(name=name,email=email,subject=subject,message=message,time=time)
                db.session.add(data)
                db.session.commit()
                flash("Email sent", "sucess")
            return render_template('index.html')
        return render_template('index.html')
    else:
        username = session['username']
        check = User.query.filter_by(username=username).first()
        checkActivated = check.activated 

        if checkActivated != 1:
            return render_template('verification.html')
            # elif request.method == 'POST':
            username = getname(request.form['username'])
            return render_template('index.html', data=getfollowedby(username))
        else:
            return render_template('index.html')
        
        return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    else:
        username = request.form['username']
        passw = request.form['password']
        try:
            data = User.query.filter_by(username=username, password=passw).first()
            if username == '' or passw =='':
                flash("Fields must not be left blank", "warning")
            else:
                if data is not None:
                    session['logged_in'] = True
                    session['username'] = request.form['username']
                    return redirect(url_for('index'))
                else:
                    flash("Something seems incorrect. Please try again", "danger")
            return redirect(url_for('login'))
        except:
            return "Dont Login"

@app.route('/login/google')
def google():
    google = oauth.create_client('google')  # create the google oauth client
    redirect_uri = url_for('authorize', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/login/google/authorize')
def authorize():
    google = oauth.create_client('google')  # create the google oauth client
    token = google.authorize_access_token()  # Access token from google (needed to get user info)
    resp = google.get('userinfo')  # userinfo contains stuff u specificed in the scrope
    user_info = resp.json()
    user = oauth.google.userinfo()  # uses openid endpoint to fetch user info
    # Here you use the profile/user data that you got and query your database find/register the user
    # and set ur own data in the session not the profile from google
    email=user_info["email"]
    check = User.query.filter_by(email=email).first()
    name=user_info["given_name"]+' '+user_info["family_name"]
    username=user_info["given_name"]+''.join(random.choices(string.ascii_letters + string.digits, k=8))
    session['username'] = username
    checkUsername = User.query.filter_by(username=username).first()
    if check:
        session['logged_in'] = True
        session['username'] = check.username
        return redirect('/')
    else:
        if checkUsername:
            username=user_info["given_name"]+''.join(random.choices(string.ascii_letters + string.digits, k=4))
            return redirect('username exisits soo')
        else:
            new_user = User(email=user_info["email"],
            name=user_info["given_name"]+' '+user_info["family_name"],
            username=username,
            password=user_info["given_name"]+''.join(random.choices(string.ascii_letters + string.digits, k=10)),
            activated=1,
            isAdmin=0,
            dateTime=datetime.datetime.now(),)
            db.session.add(new_user)
            db.session.commit()

            # session['username'] = user_info["given_name"]+' '+user_info["family_name"]
            session['username'] = username
            session['logged_in'] = True
            session.permanent = True  # make the session permanant so it keeps existing after broweser gets closed
            return redirect('/')

#This route is for sending mail to the user 
@app.route('/login/forgot/',methods=["GET","POST"])
def forgot():
     
     if request.method == 'GET':
        #  if request.method=="POST":
        # email = request.form['email']
        # check = User.query.filter_by(email=email).first()

        # if check:
        #     hashCode = ''.join(random.choices(string.ascii_letters + string.digits, k=24))
        #     check.hashCode = hashCode
        #     db.session.commit()
        #     msg = Message('Confirm Password Change', sender = 'Rujan Shrestha', recipients = [email])
        #     msg.body = "Hello,\nWe've received a request to reset your password. If you want to reset your password, click the link below and enter your new password\n http://localhost:5000/forgot/" + check.hashCode
        #     postd.send(msg)
        #     return render_template('forgot.html')

        # return '<form action="/login/forgot/" method="POST"><input name="email"><input type="submit"></form>'
        return render_template('forgot.html')
 
    
     if request.method=="POST":
        email = request.form['email']
        session['email'] = email
        check = User.query.filter_by(email=email).first()
        if check:
            
            token = s.dumps(email, salt='email-confirm')

            msg = Message('Confirm Email', sender='Rujan Shrestha', recipients=[email])

            link = url_for('confirm_email', token=token, _external=True)

            msg.body = "Hello,\nWe've received a request to reset your password. If you want to reset your password, click the link below and enter your new password\n {} .This link expires after 1 hour. Godspeed".format(link)

            postd.send(msg)
            flash("Message sent, Check your mail", "success")
            return render_template('forgot.html')


    
@app.route("/login/forgot/<token>",methods=["GET","POST"])
def confirm_email(token):
    try:
        email = s.loads(token, salt='email-confirm', max_age=3600)
    except SignatureExpired:
        return render_template('tokenexpired.html')
    if request.method == 'POST':
            passw = request.form['passw']
            cpassw = request.form['cpassw']
            if passw == cpassw:
                check.password = passw
                db.session.commit()
                session['email'] = 0
                return redirect(url_for('index'))
            else:
                flash("Password does not match, try again", "warning")
                return render_template('password.html')
    else:
        return render_template('password.html')

# def hashcode(hashCode):
#     check = User.query.filter_by(hashCode=hashCode).first()    
#     if check:
#         if request.method == 'POST':
#             passw = request.form['passw']
#             cpassw = request.form['cpassw']
#             if passw == cpassw:
#                 check.password = passw
#                 check.hashCode= None
#                 db.session.commit()
#                 return redirect(url_for('index'))
#             else:
#                 flash('yanlış girdin')
#                 return render_template('password.html')
#         else:
#             return render_template('password.html')
#     else:
#         return render_template('/')

@app.route('/register/', methods=['GET', 'POST'])
def register():
    """Register Form"""
    if session.get('logged_in'):
        return redirect(url_for('profile'))
    else:
        if request.method == 'POST':
            name=request.form['name']
            username=request.form['username']
            email=request.form['email']
            password=request.form['password']
            activated=0
            isAdmin=0
            dateTime=datetime.datetime.now()
            checkusername = User.query.filter_by(username=username).first()
            checkemail = User.query.filter_by(email=email).first()      
            if name == '' or username == '' or email == '' or password =='':
                flash("Fields must not be left blank", "warning")
            elif checkusername:
                flash("Username already exists", "warning")
            elif checkemail:
                flash("Email already exists", "warning")
            else: 
                new_user = User(
                    name=request.form['name'],
                    username=request.form['username'],
                    email=request.form['email'],
                    password=request.form['password'],
                    activated=0,
                    isAdmin=0,
                    dateTime=datetime.datetime.now(),)
                db.session.add(new_user)
                db.session.commit()
                flash("Account Created", "success")

                return render_template('login.html')
        return render_template('register.html')

@app.route('/register/verification/',methods=["GET","POST"])
def verification():
     
     if request.method == 'GET':
        #  if request.method=="POST":
        # email = request.form['email']
        # check = User.query.filter_by(email=email).first()

        # if check:
        #     hashCode = ''.join(random.choices(string.ascii_letters + string.digits, k=24))
        #     check.hashCode = hashCode
        #     db.session.commit()
        #     msg = Message('Confirm Password Change', sender = 'Rujan Shrestha', recipients = [email])
        #     msg.body = "Hello,\nWe've received a request to reset your password. If you want to reset your password, click the link below and enter your new password\n http://localhost:5000/forgot/" + check.hashCode
        #     postd.send(msg)
        #     return render_template('forgot.html')

        # return '<form action="/login/forgot/" method="POST"><input name="email"><input type="submit"></form>'
        username = session['username']
        check = User.query.filter_by(username=username).first()
        email = check.email
        session['email'] = email
        if check:
            
            token = s.dumps(email, salt='email-confirm')

            msg = Message('Confirm Email', sender='Rujan Shrestha', recipients=[email])

            link = url_for('confirm_verification', token=token, _external=True)

            msg.body = "Hello,\nWe've received a request to verify your account. To do so, click the link below \n {} .This link expires after 1 hour. Godspeed".format(link)

            postd.send(msg)
            flash('Mail sent','success')
            return render_template('verification.html')
 

@app.route('/register/verification/<token>',methods=["GET","POST"])
def confirm_verification(token):
    if request.method == 'GET':
        username = session['username']
        check = User.query.filter_by(username=username).first() 
        email = check.email
        try:
            email = s.loads(token, salt='email-confirm', max_age=3600)
        except SignatureExpired:
            return render_template('tokenexpired.html')
        else:
            check.activated = 1
            db.session.commit()
            return render_template('index.html')
    else:
        return 'hello'

@app.route("/logout")
def logout():
    """Logout Form"""
    session['logged_in'] = False
    session.pop('username',None)
    session.pop('email',None)
    return redirect(url_for('index'))

#This is the index route where we are going to
#query on all our employee data
@app.route('/admin', methods = ['GET', 'POST'])
def admin():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    else:
        username = session['username']
        # username = "admin"
        check = User.query.filter_by(username=username).first()   
        all_data = User.query.all()
        pics = UploadImage.query.all()
        articles = Discuss.query.all()
        article = Article.query.all()
        messages = ContactUs.query.all()

        if request.method == 'POST':
            user_id = check.id
            body = request.form['body']
            upload_date=datetime.datetime.now()
            new_post = Discuss(body, user_id,upload_date)
            db.session.add(new_post)
            db.session.commit()
            return redirect(url_for('admin'))
    
        return render_template("admin.html", pics=pics,check=check,articles=articles,alluser=all_data,article=article,messages=messages)
 
 
 
#this route is for inserting data to mysql database via html forms
@app.route('/admin/insert', methods = ['POST'])
def insert():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    else:
        if request.method == 'POST':
            
            name = request.form['name']
            username = request.form['username']
            email = request.form['email']
            activated = request.form.get('activated')
            password = request.form['password']
            admin = request.form.get('admin')

            my_data = User(name=name,username=username, email=email,activated=activated, isAdmin=admin, password=password,dateTime = datetime.datetime.now())
            db.session.add(my_data)
            db.session.commit()
    
            flash("User Inserted Successfully")
    
            return redirect(url_for('admin'))
 
 
#this is our update route where we are going to update our employee
@app.route('/admin/update/', methods = ['GET', 'POST'])
def update():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    else:
        if request.method == 'POST':
            my_data = User.query.get(request.form.get('id'))
    
            my_data.username = request.form['username']
            my_data.email = request.form['email']
            my_data.activated = request.form.get('activated')
            my_data.name = request.form['name']
            my_data.admin = request.form.get('admin')
            my_data.dateTime=datetime.datetime.now()

            db.session.commit()
            flash("User Updated Successfully","sucess")
    
            return redirect(url_for('admin'))
 
 
#This route is for deleting our employee
@app.route('/admin/delete/<id>/', methods = ['GET', 'POST'])
def delete(id):
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    else:
        my_data = User.query.get(id)
        db.session.delete(my_data)
        db.session.commit()
        flash("User Deleted Successfully")
    
        return redirect(url_for('admin'))

#Redirects to profile page
@app.route('/profile', methods = ['GET', 'POST'])
@app.route('/profile')
def profile(): 
    username = session['username']
    # username = "aa"
    check = User.query.filter_by(username=username).first()   
    if not session.get('logged_in'):
        return redirect(url_for('index'))

    elif check.isAdmin== "1" :
        return redirect(url_for('admin'))
        
    else:
        alluser = User.query.all()
        email = check.email 
        session['email'] = email 
        pics = UploadImage.query.all()
        articles = Discuss.query.all()
        article = Article.query.all()
        if request.method == 'POST':
            user_id = check.id
            content = request.form['content']
            if not content:
                upload_date=datetime.datetime.now()
                new_post = Discuss(content, user_id,upload_date)
                db.session.add(new_post)
                db.session.commit()
                flash("User Inserted Successfully", "sucess")
                return redirect(url_for('profile'))
            else:
                flash("Message empty", "warning")
        
        return render_template("profile.html",pics=pics,check=check,articles=articles,alluser=alluser,article=article)

@app.route('/profile/username/', methods = ['GET', 'POST'])
def username():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    else:
        username = session['username']
        check = User.query.filter_by(username=username).first()
        # if request.method == 'POST':
        #     username = session['username']
        #     my_data = User.query.get(request.form.get('username'))
    
        #     my_data.username = request.form['username']
    
        #     db.session.commit()
    
        #     return redirect(url_for('username'))
        if request.method == 'POST':
                usnam = request.form['usnam']
                cusnam = request.form['cusnam']
                if usnam == cusnam:
                    check.username = usnam
                    db.session.commit()
                    session['username'] = usnam
                    return redirect(url_for('profile'))
                else:
                    flash("Username does not match", "warning")
                    return render_template("changeUsername.html")
        else:
            return render_template("changeUsername.html")

@app.route("/profile/password/",methods=["GET","POST"])
def cpassword():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    else:
        username = session['username']
        print('username')
        check = User.query.filter_by(username=username).first()
        # email = session['email']
        # check = User.query.filter_by(email=email).first()    
        if request.method == 'POST':
                passw = request.form['passw']
                cpassw = request.form['cpassw']
                if passw == cpassw:
                    check.password = passw
                    db.session.commit()
                    return redirect(url_for('profile'))
                else:
                    flash("Password does not match", "warning")
                    return render_template("changePassword.html")
        else:
            return render_template('changePassword.html')

@app.route('/history')
def history(): 
    pics = UploadImage.query.all()
    if pics: # This is because when you first run the app, if no pics in the db it will give you an error
        all_pics = pics
        if request.method == 'POST':

            flash('Upload succesful!')
            return redirect(url_for('upload'))  

        return render_template('history.html', all_pic=all_pics)
    else:
        return render_template('history.html')

def render_picture(data):

    render_pic = base64.b64encode(data).decode('ascii') 
    return render_pic

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    else:
        username = session['username']
        # username = "aa"
        check = User.query.filter_by(username=username).first()
        userId = check.id
        # file = request.files['file']
        # data = request.files['file'].read()
        pics = UploadImage.query.all()
        UPLOAD_FOLDER = 'app/static/input/before'
        app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

        if request.method == 'POST':

            file = request.files['file']
            # check if the post request has the file part
            if 'file' not in request.files:
                flash("No file part","warning")
                return redirect(url_for('profile'))
            # file = request.files['file']
            # if user does not select file, browser also
            # submit an empty part without filename
            if file.filename == '':
                flash("No files selected", "warning")
                return redirect(url_for('profile'))

            if not allowed_file(file.filename):
                flash("Must be a JPEG file", "warning")
                return redirect(url_for('profile'))

            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

                modelName= request.form.get('chooseModel')
                data = file.read()
                render_file = render_picture(data)
                newFile = UploadImage(name=file.filename, data=data, rendered_data=render_file,user_id=userId,model_name=modelName)
                db.session.add(newFile)
                db.session.commit()

                
                img = os.system("python upscale.py models\..\models\\" + modelName+".pth"+" -i app/static/input/before/ -o app/static/output")
                
                # img = cv2.imread(path, cv2.IMREAD_COLOR)
    
            return redirect(url_for('profile'))
            # return redirect(cwd)
        

# @app.route('/upload', methods=['POST'])
# def upload():
#    username = session['username']
#    check = User.query.filter_by(username=username).first()
#    userId = check.id
#    file = request.files['inputFile']
#    data = file.read()
#    pics = UploadImage.query.all()
#    render_file = render_picture(data)

#    newFile = UploadImage(name=file.filename, data=data, rendered_data=render_file,user_id=userId)
#    db.session.add(newFile)
#    db.session.commit() 
# #    flash(f'Pic {newFile.name}')

#    return redirect(url_for('profile'))


# Show Pic
@app.route('/pic/<int:pic_id>')
def pic(pic_id):

    get_pic = UploadImage.query.filter_by(id=pic_id).first()

    return render_template('profile.html', pic=get_pic)

# Download
# @app.route('/download/<int:pic_id>')
# def download(pic_id):
#     file_data = UploadImage.query.filter_by(id=pic_id).first()
#     filename = file_data.name
#     uploads = os.path.join(app.config['UPLOAD_FOLDER'])
#     return send_from_directory(directory=uploads, filename=filename)
#     # return send_file(BytesIO(file_data.data), attachment_filename=file_name, as_attachment=True)

@app.route('/download/<path:filename>')
def download(filename):
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    else:
        UPLOAD_FOLDER = 'static/output/'
        app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
        file_data = UploadImage.query.filter_by(id=filename).first()
        # filename = file_data.name
        uploads = os.path.join(app.config['UPLOAD_FOLDER'])+filename
        # return send_from_directory(directory=uploads, filename=filename)
        return send_file(uploads, as_attachment=True, attachment_filename='')

#Delete
# @app.route('/<int:pic_id>/delete', methods=['GET', 'POST'])
# def deletePic(pic_id):
#     del_pic = UploadImage.query.get(pic_id)
#     if request.method == 'POST':
#         form = request.form['delete']
#         if form == 'Delete':
#             print(del_pic.name)
#             db.session.deletePic(del_pic)
#             db.session.commit()
#             return redirect(url_for('history'))
#     return redirect(url_for('history'))

# @app.route('/delete/<path:filename>')
# def image_delete(filename):
#     del_pic = UploadImage.query.get(filename)
#     UPLOAD_FOLDER = 'app/static/output/'
#     app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
#     file_data = UploadImage.query.filter_by(id=filename).first()
#     # filename = file_data.name
#     # os.remove((app.config['UPLOAD_FOLDER'])+filename)
#     db.session.image_delete(del_pic)
#     db.session.commit()
#     # return send_from_directory(directory=uploads, filename=filename)
#     return redirect(url_for('profile'))

@app.route('/discuss', methods = ['GET', 'POST'])
def discuss():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    else:
        username = session['username']
        # username = "aa"
        check = User.query.filter_by(username=username).first()   
        alluser = User.query.all()
        email = check.email 
        session['email'] = email 
        pics = UploadImage.query.all()
        articles = Discuss.query.all()
        article = Article.query.all()
        
        if request.method == 'POST':
            user_id = check.id
            body = request.form['body']
            upload_date=datetime.datetime.now()
            new_post = Discuss(body, user_id,upload_date)
            db.session.add(new_post)
            db.session.commit()
            return redirect(url_for('discuss'))
                            
        
        return render_template("discuss.html",pics=pics,check=check,articles=articles,alluser=alluser,article=article)

@app.route('/article', methods = ['GET', 'POST'])
def article(): 
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    else:
        username = session['username']
        # username = "aa"
        check = User.query.filter_by(username=username).first()   
        alluser = User.query.all()

        pics = UploadImage.query.all()
        articles = Article.query.all()

        UPLOAD_FOLDER = 'app/static/article'
        app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

        if request.method == 'POST':
                user_id = check.id
                title = request.form['title']
                body = request.form['body']
                modelName= request.form.get('chooseModel')
                file = request.files["file"]
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))


                upload_date=datetime.datetime.now()
                new_post = Article(title=title,body=body,user_id=user_id,upload_date=upload_date,img_name=filename,model=modelName)
                db.session.add(new_post)
                db.session.commit()
                return redirect(url_for('discuss'))
                
        
        return render_template("discuss.html",pics=pics,check=check,articles=articles,alluser=alluser)

@app.route('/article/<int:article_id>') 
def articles(article_id):
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    else:
        username = session['username']
        # username = "admin"
        check = User.query.filter_by(username=username).first()  
        alluser = User.query.all()
        article = Article.query.filter_by(id=article_id).first()
        
        return render_template('article.html', article=article,alluser=alluser,check=check)

#this is our update route where we are going to update our employee
@app.route('/article/edit/<int:article_id>', methods = ['GET', 'POST'])
def updateArticle(article_id):
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    else:
        username = session['username']
        check = User.query.filter_by(username=username).first()  
        article_id = article_id
        alluser = User.query.all()
        article = Article.query.filter_by(id=article_id).first()
        # art = User.query.get(article_id)
        UPLOAD_FOLDER = 'app/static/article'
        app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
        if request.method == 'POST':
        
            file = request.files['file']
            # check if the post request has the file part
            if 'file' not in request.files:
                flash("No file part","warning")
                return redirect(url_for('updateArticle',article_id=article_id))
            # file = request.files['file']
            # if user does not select file, browser also
            # submit an empty part without filename
            if file.filename == '':
                flash("No files selected", "warning")
                return redirect(url_for('updateArticle',article_id=article_id))

            if not allowed_file(file.filename):
                flash("Must be a JPEG file", "warning")
                return redirect(url_for('updateArticle',article_id=article_id))

            if file and allowed_file(file.filename):
                upload_date=datetime.datetime.now()
                article.title = request.form['title']
                article.body = request.form['body']
                article.modelName= request.form.get('chooseModel')
                article.img_name = filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                db.session.commit()
                flash("Article Updated Successfully")

        if check.isAdmin == "1":
            return render_template('admin.html' , article=article,alluser=alluser)
        else:
            return render_template('updateart.html' , article=article,alluser=alluser)
        # return redirect(article)

@app.route('/article/delete/<int:article_id>', methods = ['GET', 'POST'])
def deleteArticle(article_id):
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    else:
        username = session['username']
        check = User.query.filter_by(username=username).first()  
        my_data = Article.query.get(article_id)
        db.session.delete(my_data)
        db.session.commit()
        flash("User Deleted Successfully")
        admin = check.isAdmin

        if check.isAdmin == "1":
            return redirect(url_for('admin'))
        else:
            return redirect(url_for('discuss'))
 