from flask import render_template, request, redirect, flash, url_for, send_from_directory
from sp_app import app, db
import os
from sp_app.forms import LoginForm, ChangePassword
from flask_login import current_user, login_user, logout_user
from sp_app.models import ReferenceSequence, SPDataSet, DataSetSample, DataAnalysis, CladeCollection, AnalysisType, Study, SPUser
from werkzeug.urls import url_parse
from sqlalchemy import or_
from sqlalchemy.orm.exc import NoResultFound
import json
import ntpath


@app.route('/', methods=['GET','POST'])
@app.route('/index', methods=['GET','POST'])
def index():
    if request.method == 'GET':
        # get the studies that will be loaded into the published data set table
        published_studies = Study.query.filter(Study.is_published==True, Study.display_online==True).all()
        
        # get the studies that belong to the user that are not yet published
        try:
            sp_user = SPUser.query.filter(SPUser.name==current_user.name).one()
            user_unpublished_studies = [study for study in Study.query.filter(Study.is_published==False, Study.display_online==True) if sp_user in study.users]
        except AttributeError as e:
            user_unpublished_studies = []
        except NoResultFound:
            # We should never get here as we have checked for this at the login route.
            logout_user()
            return redirect(url_for('index'))


        # Finally get the resource_info_dict that is jsoned out and pass this in
        json_resource_info_dict_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'static', 'resources', 'resource_info.json')
        with open(json_resource_info_dict_path, 'r') as f:
            resource_info_dict = dict(json.load(f))
        return render_template('index.html', published_studies=published_studies, user_unpublished_studies=user_unpublished_studies, resource_info_dict=resource_info_dict)

@app.route('/data_explorer/', methods=['POST'])
def data_explorer():
    # get the google maps api key to be used
    map_key_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'static', 'utils', 'google_maps_api_key.txt')
    with open(map_key_path) as f:
        map_key = f.read().rstrip()
    # Here we are going to load the data_explorer page
    # We will need to provide the database object that represents the study_to_load string
    # provided by the request.
    # We will also need to provide a list of studies to load in the dataexplorer drop
    # down that allows users to switch between the DataSet that they are viewing
    study_to_load = Study.query.filter(Study.name==request.form.get('study_to_load')).first()
    # The other studies should be those that are:
    # a - published
    # b - have dataexplorer data
    # c - are unpublished but have the current user in their users_with_access list
    # We also want to exclude the study_to_load study.
    if current_user.is_anonymous:
        published_and_authorised_studies = Study.query\
            .filter(Study.data_explorer==True, Study.is_published==True, Study.display_online==True).all()
    elif current_user.is_admin:
        # If user is admin then we just want to display all of the studies that have dataexplorer available
        # regardless of whether the user is in the users_with_access list
        published_and_authorised_studies = Study.query.filter(Study.data_explorer==True, Study.display_online==True).all()
    else:
        # If not admin but signed in, then we want to return the published articles
        # and those that the user is authorised to have.
        sp_user = SPUser.query.filter(SPUser.name==current_user.name).one()
        published_and_authorised_studies = Study.query.filter(Study.data_explorer==True, Study.display_online==True)\
            .filter(or_(Study.is_published==True, Study.users.contains(sp_user)))\
            .filter(Study.name != study_to_load.name).all()
    return render_template('data_explorer.html', study_to_load=study_to_load,
                           published_and_authorised_studies=published_and_authorised_studies, map_key=map_key)

EXPLORER_DATA_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'explorer_data')
@app.route('/get_study_data/<string:study_name>/<path:file_path>/')
def get_study_data(study_name, file_path):
    # This route will be picked up whenever we want to load the data explorer page
    # If the study is published or belongs to the currently logged in user, it will
    # return the study_data.js file of the corresponding study
    # Else it will return to index

    # If the study requested is published, send the study_data.js
    file_dir = os.path.join(EXPLORER_DATA_DIR, study_name, os.path.dirname(file_path))
    filename = ntpath.basename(file_path)
    study_obj = Study.query.filter(Study.name == study_name).one()

    # NB if the current user is anonymous and we try to call .is_admin, we get an attribute error
    if not study_obj.is_published:
        if current_user.is_anonymous:
            # Then divert to index
            # This code shouldn't be reachable as study links won't be displayed to a non-logged in user
            # unless they are public
            return redirect(url_for('index'))
        else:
            sp_user = SPUser.query.filter(SPUser.name == current_user.name).one()
            if (sp_user in study_obj.users) or current_user.is_admin:
                # Then this study belongs to the logged in user and we should release the data
                # Or the user is an admin and we should release the data
                if filename == 'study_data.js':
                    print(f'returning {os.path.join(file_dir, filename)}')
                    return send_from_directory(directory=file_dir, filename=filename)
                else:
                    print(f'returning {os.path.join(file_dir, filename)}')
                    return send_from_directory(directory=file_dir, filename=filename, as_attachment=True)
            else:
                return redirect(url_for('index'))
    else:
        # Study is published
        if filename == 'study_data.js':
            print(f'returning {os.path.join(file_dir, filename)}')
            return send_from_directory(directory=file_dir, filename=filename)
        else:
            print(f'returning {os.path.join(file_dir, filename)}')
            return send_from_directory(directory=file_dir, filename=filename, as_attachment=True)

@app.route('/submit_data_learn_more')
def submit_data_learn_more():
    return render_template('submit_data_learn_more.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = SPUser.query.filter(SPUser.name==form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash("Invalid username or password")
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('index')
        return redirect(next_page)
    return render_template('login.html', form=form)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if current_user.is_anonymous:
        return redirect(url_for('index'))
    form=ChangePassword()
    if form.validate_on_submit():
        user = SPUser.query.filter_by(name=form.username.data).first()
        if user is None or not user.check_password(form.current_password.data):
            print("Invalid username or password")
            flash("Invalid username or password")
            return redirect(url_for('change_password'))
        else:
            # Then the password username was good and we should change the password for the user
            user.set_password(form.new_password.data)
            db.session.commit()
            flash("Password successfully changed")
            print("Password successfully changed")
            return redirect(url_for('index'))
    # We reach here if this is the first navigation to this page
    return render_template('change_password.html', form=form)


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if request.method == 'GET':
        if current_user.is_anonymous:
            return redirect(url_for('index'))
        # We will populate a table that shows the studies that the user is authorised for
        sp_user = SPUser.query.filter(SPUser.name==current_user.name).one()
        user_authorised_studies = list(Study.query.filter(Study.users.contains(sp_user), Study.display_online==True).all())
        # We will also populate a table that will only be visible is the user is an admin
        # This table will be populated with all unpublished studies that the user is not authorised on (these will be shown above)
        if current_user.is_admin:
            admin_authorised_studies = list(Study.query.filter(~Study.is_published).filter(~Study.users.contains(sp_user)).filter(Study.display_online==True).all())
        else:
            admin_authorised_studies= list()
        return render_template('profile.html', user_authorised_studies=user_authorised_studies, admin_authorised_studies=admin_authorised_studies)
    if request.method == 'POST':
        # Then someone has clicked on one of the study titles
        # and we should send them to the DataExplorer view of respective study
        # get the google maps api key to be used
        map_key = os.environ.get('GOOGLE_MAPS_API_KEI')
        # Here we are going to load the data_explorer page
        # We will need to provide the database object that represents the study_to_load string
        # provided by the request.
        # We will also need to provide a list of studies to load in the dataexplorer drop
        # down that allows users to switch between the DataSet that they are viewing
        study_to_load = Study.query.filter(Study.name==request.form.get('study_to_load')).first()
        # The other studies should be those that are:
        # a - published
        # b - have dataexplorer data
        # c - are unpublished but have the current user in their users_with_access list
        # We also want to exclude the study_to_load study.
        if current_user.is_anonymous:
            published_and_authorised_studies = Study.query.filter(Study.data_explorer==True, Study.is_published==True, Study.display_online==True).all()
        elif current_user.is_admin:
            # If user is admin then we just want to display all of the studies that have dataexplorer available
            # regardless of whether the user is in the users_with_access list
            published_and_authorised_studies = Study.query.filter(Study.data_explorer==True, Study.display_online==True).all()
        else:
            sp_user = SPUser.query.filter(SPUser.name==current_user.name).one()
            # If not admin but signed in, then we want to return the published articles
            # and those that the user is authorised to have.
            published_and_authorised_studies = Study.query.filter(Study.data_explorer==True, Study.display_online==True)\
                .filter(or_(Study.is_published==True, Study.users.contains(sp_user)))\
                .filter(Study.name != study_to_load.name).all()
        return render_template('data_explorer.html', study_to_load=study_to_load,
                               published_and_authorised_studies=published_and_authorised_studies ,map_key=map_key)