from flask import render_template, request, redirect, flash, url_for, jsonify, send_from_directory
from sp_app import app, db
import os
from sp_app.forms import LoginForm, ChangePassword
from flask_login import current_user, login_user, logout_user, login_required
from sp_app.models import ReferenceSequence, SPDataSet, DataSetSample, DataAnalysis, CladeCollection, AnalysisType, Study, SPUser, Submission
from werkzeug.urls import url_parse
from sqlalchemy.orm.exc import NoResultFound
import json
from sp_app.datasheet_check import DatasheetChecker, DatasheetGeneralFormattingError, AddedFilesError, UploadedFilesError, DateFormatError, LatLonError
import shutil
import traceback
import ntpath
import pandas as pd
from werkzeug.utils import secure_filename
from datetime import datetime
import subprocess
from subprocess import CalledProcessError
import stat
from sqlalchemy import or_
import warnings

# for mailing feature
from symportal_kitchen.email_notifications.submission_status import send_email

# As we start to work with the remote database we will want to minimise calls to it.
# As such we will make an initial call to get all studies
# We have specified some lazy='joined' calls in the models.py file so that
# we collect all required information in one connection to the database.
# If we modify the database in any way (we don't do this yet), we will explicitly call code to update this variable
# so that our queries are still up to date.
# Once this variable is set, we can work with the ORM objects for the remainder of the routes.py
@app.route('/', methods=['GET','POST'])
@app.route('/index', methods=['GET','POST'])
def index():
    if request.method == 'GET':
        # get the studies that will be loaded into the published data set table
        published_studies = [study for study in Study.query.all() if study.is_published is True and study.display_online is True]

        # get the studies that belong to the user that are not yet published
        try:
            sp_user = SPUser.query.filter(SPUser.name==current_user.name).one()
            if sp_user.is_admin: # List all pending submissions
                user_pending_submissions = Submission.query.all()
            else:
                user_pending_submissions = [sub for sub in Submission.query.all() if sub.submitting_user_id == sp_user.id]
            user_unpublished_studies = [study for study in Study.query.filter(Study.is_published==False, Study.display_online==True) if sp_user in study.users]
        except AttributeError as e:
            # Anonymous user
            user_unpublished_studies = []
            user_pending_submissions = []
        except NoResultFound:
            # We should never get here as we have checked for this at the login route.
            logout_user()
            return redirect(url_for('index'))
        # Finally get the resource_info_dict that is jsoned out and pass this in
        json_resource_info_dict_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'static', 'resources', 'resource_info.json')
        with open(json_resource_info_dict_path, 'r') as f:
            resource_info_dict = dict(json.load(f))
        # Use a Bool temporarily to enable access to the submission page
        if current_user.is_anonymous:
            allow_submission = False
        else:
            if current_user.has_upload_permission or current_user.is_admin:
                allow_submission = True
            else:
                allow_submission = False
        return render_template(
            'index.html',
            published_studies=published_studies,
            user_unpublished_studies=user_unpublished_studies,
            resource_info_dict=resource_info_dict,
            user_pending_submissions=user_pending_submissions,
            allow_submission=allow_submission,
            email_address=os.getenv('CONTACT_EMAIL_ADDRESS')
        )

def get_spuser_by_name_from_orm_spuser_list(user_to_match):
    """ A sort of wrapper method that gets an ORM object that is the SPUser object from
    the currently logged in user.
    """
    sp_user = [spuser for spuser in SPUser.query.all() if spuser.name == user_to_match.username]
    assert (len(sp_user) == 1)
    return sp_user[0]

def get_study_by_name_from_orm_study_list(study_name_to_match):
    """ A sort of wrapper method that gets an ORM object that is the Study object from
    a study name.
    """
    study = [study for study in Study.query.all() if study.name == study_name_to_match]
    assert (len(study) == 1)
    return study[0]

@app.route('/data_explorer/', methods=['POST'])
def data_explorer():
    # get the google maps api key to be used
    map_key = os.environ.get('GOOGLE_MAPS_API_KEY')
    # Here we are going to load the data_explorer page
    # We will need to provide the database object that represents the study_to_load string
    # provided by the request.
    # We will also need to provide a list of studies to load in the dataexplorer drop
    # down that allows users to switch between the DataSet that they are viewing
    study_to_load = get_study_by_name_from_orm_study_list(study_name_to_match=request.form.get('study_to_load'))
    # The other studies should be those that are:
    # a - published
    # b - have dataexplorer data
    # c - are unpublished but have the current user in their users_with_access list
    # We also want to exclude the study_to_load study.
    if current_user.is_anonymous:
        published_and_authorised_studies = [study for study in Study.query.all() if study.data_explorer and study.is_published and study.display_online]
    elif current_user.is_admin:
        # If user is admin then we just want to display all of the studies that have dataexplorer available
        # regardless of whether the user is in the users_with_access list
        published_and_authorised_studies = [study for study in Study.query.all() if study.data_explorer and study.display_online]
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
    study_obj = get_study_by_name_from_orm_study_list(study_name_to_match=study_name)

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
                    return send_from_directory(directory=file_dir,
                                               path=filename)
                else:
                    print(f'returning {os.path.join(file_dir, filename)}')
                    return send_from_directory(directory=file_dir,
                                               path=filename,
                                               as_attachment=True)
            else:
                return redirect(url_for('index'))
    else:
        # Study is published
        if filename == 'study_data.js':
            print(f'returning {os.path.join(file_dir, filename)}')
            return send_from_directory(directory=file_dir, path=filename)
        else:
            print(f'returning {os.path.join(file_dir, filename)}')
            return send_from_directory(directory=file_dir, path=filename,
                                       as_attachment=True)

@app.route('/submit_data_learn_more')
def submit_data_learn_more():
    return render_template('submit_data_learn_more.html', email_address=os.getenv('CONTACT_EMAIL_ADDRESS'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:

        # Log the user authentication debug
        app.logger.debug(f'User {current_user.name} is already authenticated')

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

        # Log the user authentication info
        app.logger.info(f'User {current_user.name} is authenticated')

        return redirect(next_page)
    return render_template('login.html', form=form, email_address=os.getenv('CONTACT_EMAIL_ADDRESS'))

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
            admin_authorised_studies = [
                study for study in Study.query.all() if
                not study.is_published and not sp_user in study.users and study.display_online]
        else:
            admin_authorised_studies = []
        return render_template('profile.html', user_authorised_studies=user_authorised_studies, admin_authorised_studies=admin_authorised_studies)
    if request.method == 'POST':
        # Then someone has clicked on one of the study titles
        # and we should send them to the DataExplorer view of respective study
        # get the google maps api key to be used
        map_key = os.environ.get('GOOGLE_MAPS_API_KEY')
        # Here we are going to load the data_explorer page
        # We will need to provide the database object that represents the study_to_load string
        # provided by the request.
        # We will also need to provide a list of studies to load in the dataexplorer drop
        # down that allows users to switch between the DataSet that they are viewing
        study_to_load = get_study_by_name_from_orm_study_list(study_name_to_match=request.form.get('study_to_load'))
        # The other studies should be those that are:
        # a - published
        # b - have dataexplorer data
        # c - are unpublished but have the current user in their users_with_access list
        # We also want to exclude the study_to_load study.
        if current_user.is_anonymous:
            published_and_authorised_studies = [study for study in Study.query.all() if study.data_explorer and study.is_published and study.display_online]
        elif current_user.is_admin:
            # If user is admin then we just want to display all of the studies that have dataexplorer available
            # regardless of whether the user is in the users_with_access list
            published_and_authorised_studies = [study for study in Study.query.all() if study.data_explorer and study.display_online]
        else:
            sp_user = SPUser.query.filter(SPUser.name==current_user.name).one()
            # If not admin but signed in, then we want to return the published articles
            # and those that the user is authorised to have.
            published_and_authorised_studies = [
                study for study in Study.query.all() if
                study.data_explorer and study.display_online and study.name != study_to_load.name and
                (study.is_published or sp_user in study.users)
            ]
        return render_template('data_explorer.html', study_to_load=study_to_load,
                               published_and_authorised_studies=published_and_authorised_studies ,map_key=map_key)

# Max upload size
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 * 1024

# file Upload
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'uploads')
# Make directory if "uploads" folder not exists
if not os.path.isdir(UPLOAD_FOLDER):
    os.mkdir(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/submission', methods=['GET', 'POST'])
@login_required
def upload_data():
    if request.method == 'GET':
        # Check to see that the user requesting the page is allowed to perform an upload
        # I.e. to prevent users by passing navigation controls
        if current_user.is_anonymous:
            return redirect(url_for('index'))
        if current_user.is_admin:
            return render_template('submission.html', current_users=SPUser.query.order_by(SPUser.name).all(), assign_user=True)
        elif current_user.has_upload_permission:
            return render_template('submission.html', assign_user=False)
        else:
            return redirect(url_for('index'))

@app.route('/_check_submission', methods=['POST'])
@login_required
def _check_submission():
    """
    This is called when a user selects a new data sheet or new seq files.
    This is also called when a user clicks the #start_upload_btn, to upload either the datasheet or
    the seq files.
    """
    # Ignore the: UserWarning: Data Validation extension is not supported and will be removed
    # that we get when reading in the excel sheet in pandas
    warnings.simplefilter(action='ignore', category=UserWarning)
    if not request.files:
    # Then this is checking files in the staged area, i.e. files have been added (selected from the users OS file
    # system) or removed from the staging area.
        # We have created a data_dict json object and sent it up with the form.
        data_dict = json.loads(list(request.form.keys())[0])
        if data_dict["add_or_upload"] == "add" and data_dict["datasheet_data"] == "":
            # Then the user has selected a datasheet from their OS file system and we do very basic checks
            # to see that it is a single file and that it has the correct extension
            if len(data_dict["files"]) != 1:
                response = {
                    "check_type": "datasheet",
                    "add_or_upload": "add",
                    "error":True,
                    "border_class": "border-danger",
                    "message":'<strong class="text-danger">Please select a single datasheet (.xlsx, .csv)</strong>'
                }
                return jsonify(response)
            file_name = [k for k, v in data_dict["files"][0].items()][0]
            if file_name.endswith(".xlsx") or file_name.endswith(".csv"):
                response = {
                    "check_type": "datasheet",
                    "add_or_upload": "add",
                    "error":False,
                    "border_class": "border-success",
                    "message":'<strong class="text-success">Datasheet selected, please upload<strong>'
                }
                return jsonify(response)
            else:
                response = {
                    "check_type": "datasheet",
                    "add_or_upload": "add",
                    "error": True,
                    "border_class": "border-danger",
                    "message": '<strong class="text-danger">Please select a single datasheet (.xlsx, .csv)</strong>'
                }
                return jsonify(response)
        else:
            # Checking sequencing files that are in the staged area
            # Here we are checking to see that the currently staged seq files match those listed in the
            # datasheet and that there are no other errors with the datasheet and seq files
            try:
                datasheet_path = os.path.join(app.config['UPLOAD_FOLDER'], current_user.name, data_dict["datasheet_data"])
                dc = DatasheetChecker(
                    request=request,
                    user_upload_directory=os.path.join(app.config['UPLOAD_FOLDER'], current_user.name),
                    datasheet_path=datasheet_path)
                try:
                    dc.check_valid_seq_files_added()
                    # If we make it to here then an AddedFilesError was not raised
                    # Check to see if any of the warning containers have contents
                    # If so return these
                    if (
                            dc.binomial_dict or dc.lat_long_dict or
                            dc.lat_lon_missing or dc.date_missing_list or
                            dc.depth_missing_list or dc.sample_type_missing_list or
                            dc.taxonomy_missing_set
                    ):
                        response = {
                            "check_type": "seq_files", "add_or_upload": "add",
                            'error': False, 'warning':True,
                            "data": {
                                'binomial_dict': dc.binomial_dict,
                                'lat_long_missing': dc.lat_lon_missing,
                                'date_missing':dc.date_missing_list,
                                'depth_missing': dc.depth_missing_list,
                                'sample_type_missing':dc.sample_type_missing_list,
                                'taxonomy_missing': list(dc.taxonomy_missing_set),
                            },
                            "border_class": "border-warning"
                        }
                        return jsonify(response)

                    else:
                        # No warnings
                        response = {
                            "check_type": "seq_files", "add_or_upload": "add",
                            'error': False, 'warning': False,
                            "border_class": "border-success"
                        }
                        return jsonify(response)
                
                # TODO add Error types for bad date and bad lat long values
                # Force the user to either correct the values to appropriate values or
                # to delte the offending values
                except LatLonError as e:
                    response = {
                        "error_type": "LatLonError", "check_type": "seq_files", "add_or_upload": "add",
                        'error': True, 'message': str(e),
                        "data": e.data,
                        "border_class": "border-danger"
                    }
                    return jsonify(response)
                except DateFormatError as e:
                    response = {
                        "error_type": "DateFormatError", "check_type": "seq_files", "add_or_upload": "add",
                        'error': True, 'message': str(e),
                        "data": e.data,
                        "border_class": "border-danger"
                    }
                    return jsonify(response)
                except AddedFilesError as e:
                    # Then files were missing, too small, or extra files were added
                    response = {
                        "error_type": "AddedFilesError", "check_type": "seq_files", "add_or_upload": "add",
                        'error': True, 'message': str(e),
                        "data": e.data,
                        "border_class": "border-danger"
                    }
                    return jsonify(response)
            except Exception:
                # Catch any unhandled errors and present on to the user with a 'please contact us' message
                tb = traceback.format_exc().replace("\n", "<br>")
                response = {
                    'error': True,
                    'message': '<strong class="text-danger">ERROR: an unexpected error has occured when trying to run QC on your submission.</strong><br>'
                               'Please ensure that you are uploading a properly formatted datasheet.<br>'
                               'If the error persists, please get in contact at:<br>'
                               '&#098;&#101;&#110;&#106;&#097;&#109;&#105;&#110;&#099;&#099;&#104;&#117;&#109;&#101;&#064;&#103;&#109;&#097;&#105;&#108;&#046;&#099;&#111;&#109;<br>'
                               f'The full backend traceback is:<br><br>{tb}',
                    "error_type": "unhandled_error",
                    "response_type": "datasheet",
                    "border_class": "border-danger"
                }
                # Delete the datasheet from the server if it has been saved
                if 'dc' in locals():
                    if dc.datasheet_path:
                        if os.path.exists(dc.datasheet_path):
                            os.remove(dc.datasheet_path)
                return jsonify(response)
    else:
        # Then this is an upload of either a datasheet or sequencing files that have been checked
        # while in the staging area
        if len(request.files) == 1:
            # Then this is an upload of a datasheet
            # We should perform the general formatting tests on it and then send an appropriate response.
            # If the general formatting tests pass, we enable user to proceed to sequence upload
            # If the general checking fails then we will output the errors to show where it failed.
            # TODO display a spinner when we send it up and switch it off once checking is complete
            # can set a delay of 1 sec or something.
            try:
                dc = DatasheetChecker(
                    request=request,
                    user_upload_directory=os.path.join(app.config['UPLOAD_FOLDER'], current_user.name))
                try:
                    # TODO If we have an error here then we should first try to catch it as the
                    # DatasheetGeneralFormattingError that the we have created and then handle
                    # unhandled errors" and pass back this error to the
                    # browser to inform the user.
                    dc.do_general_format_check()
                    response = {
                        'error': False,
                        'message': f'<strong class="text-success">Datasheet {dc.datasheet_filename} '
                                   f'containing {len(dc.sample_meta_info_df.index)} '
                                   f"samples successfully uploaded.</strong><br>Please select your seq files",
                        "num_samples": len(dc.sample_meta_info_df.index),
                        "response_type": "datasheet",
                        "datasheet_filename": dc.datasheet_filename,
                        "border_class": "border-success"
                    }
                    return jsonify(response)
                except DatasheetGeneralFormattingError as e:
                    if e.data["error_type"] == "non_unique":
                        response = {
                            'error': True, 'message': str(e),
                            "data": e.data["non_unique_data"],
                            "error_type": "non_unique",
                            "response_type": "datasheet",
                            "border_class": "border-danger"
                        }
                    elif e.data["error_type"] == "full_path":
                        response = {
                            'error': True, 'message': str(e),
                            "data": e.data["example_filename"],
                            "error_type": "full_path",
                            "response_type": "datasheet",
                            "border_class": "border-danger"
                        }
                    elif e.data["error_type"] == "df_empty":
                        response = {
                            'error': True, 'message': str(e),
                            "error_type": "df_empty",
                            "response_type": "datasheet",
                            "border_class": "border-danger"
                        }
                    elif e.data["error_type"] == "invalid_file_format":
                        response = {
                            'error': True, 'message': str(e),
                            "error_type": "invalid_file_format",
                            "response_type": "datasheet",
                            "border_class": "border-danger"
                        }
                    elif e.data["error_type"] == "invalid_sample_name_format":
                        response = {
                            'error': True, 'message': str(e),
                            "error_type": "invalid_sample_name_format",
                            "response_type": "datasheet",
                            "border_class": "border-danger"
                        }
                    os.remove(dc.datasheet_path)
                    return jsonify(response)
            except Exception as e:
                # Catch any unhandled errors and present on to the user with a 'please contact us' message
                tb = traceback.format_exc().replace("\n", "<br>")
                response = {
                    'error': True,
                    'message': '<strong class="text-danger">ERROR: an unexpected error has occured when trying to run QC on your submission.</strong><br>'
                               'Please ensure that you are uploading a properly formatted datasheet.<br>'
                               'If the error persists, please get in contact at:<br>'
                               '&#098;&#101;&#110;&#106;&#097;&#109;&#105;&#110;&#099;&#099;&#104;&#117;&#109;&#101;&#064;&#103;&#109;&#097;&#105;&#108;&#046;&#099;&#111;&#109;<br>'
                               f'The full backend traceback is:<br><br>{tb}',
                    "error_type": "unhandled_error",
                    "response_type": "datasheet",
                    "border_class": "border-danger"
                }
                # Delete the datasheet from the server if it has been saved
                if 'dc' in locals():
                    if dc.datasheet_path:
                        if os.path.exists(dc.datasheet_path):
                            os.remove(dc.datasheet_path)
                return jsonify(response)
        else:
            # Then we are handling the upload of sequence data that has already been through the checking.
            # At this point we will be saving files doing final checks and then sending back good news to the user
            # Here we want to save all of the files to the local users directory

            # 1 - Check that they have not already been saved
            # 2 - save the files.
            # 3 - Check to see if all files are now saved
            # If they are then create Submission object
            # else return data that will allow us to update the staging area status
            # 4 - finally have this all wrapped in a try to catch an error.
            # Here I forsee 3 response types
            # 1 - Error of some sort
            # 2 - response after saving some files
            # 3 - Response after saving all files.

            # TODO implement the ability to upload an md5sum file that can be verified

            # Create a pending submission objects
            # TODO implement checks for unique files, I.e. md5sum and also the unique name of sequencing runs

            # TODO setup and send up the extra form that allows users to add a title and location to the
            #  submission object. This information will be used in for the Study and Dataset objects too.
            try:
                df, user_upload_path = _load_data_sheet_df()

                # get a list of file names that should be there
                # check that each of the four uploaded files are in the datasheet
                uploaded_filename_dict = {request.files[str(file_key)].filename: str(file_key) for file_key in request.files}
                saved_files = [filename for filename in os.listdir(user_upload_path) if filename.endswith('q.gz')]
                for _filename in uploaded_filename_dict.keys():
                    if _filename.endswith('fastq') or _filename.endswith('fq'):
                        response = {
                            'error': True, 'message':
                                '<strong class="text-danger">ERROR: '
                                'You are attempting to upload uncompressed fastq files. '
                                'Files must be gzipped. I.e. extension fastq.gz.</strong><br>',
                            "error_type": "invalid_file_format",
                            "response_type": "datasheet",
                            "border_class": "border-danger"
                        }
                        return jsonify(response)
                filenames_in_datasheet = list(_.strip() for _ in df['fastq_fwd_file_name'])
                filenames_in_datasheet.extend(_.strip() for _ in list(df['fastq_rev_file_name']))
                for _filename in uploaded_filename_dict.keys():
                    if _filename not in filenames_in_datasheet:
                        raise UploadedFilesError(f'{_filename} is uploaded but not found in the datasheet', data=None)
                    if _filename not in saved_files:
                        # Then save the file
                        file = request.files.get(uploaded_filename_dict[_filename])
                        secured_filename = secure_filename(file.filename)
                        file_path = os.path.join(user_upload_path, secured_filename)
                        file.save(file_path)

                # Now check to see if this batch of uploads has completed the uploads or whether files
                # still remain to be loaded.
                saved_files = [filename for filename in os.listdir(user_upload_path) if filename.endswith('q.gz')]
                if set(saved_files) == set(filenames_in_datasheet):
                    # Then we have finished we have all of the files
                    # Create a submission object
                    # The submission name will be datetime string with the username appended
                    # NB we will temporarily se framework_local_dir_path to the submission name as I don't want
                    # to hard code in the zygote path into this code. We will update this once we transfer to
                    # Zygote or whichever server is hosting the framework.
                    # Check to see if a user has been selected in the drop down and if so
                    # use this user
                    if request.form['user_drop_down_val'] != "":
                        sp_user = SPUser.query.filter(SPUser.name==request.form['user_drop_down_val']).one()
                    else:
                        sp_user = SPUser.query.filter(SPUser.name==current_user.name).one()
                    dt_string = str(datetime.utcnow()).split('.')[0].replace('-','').replace(' ','T').replace(':','')
                    submission_name = f"{dt_string}_{sp_user.name}"
                    # Now that we have a unique string for this submission, create a directory of this name
                    # and move the files that are currently saved in the more generic user directory into this
                    # submission specific directory.
                    submission_dir = os.path.join(user_upload_path, submission_name)
                    os.makedirs(submission_dir, exist_ok=False)
                    # change the file permissions so that other can execute so that the
                    # directory can be deleted remotely by the cron job from zygote
                    os.chmod(submission_dir, 0o777)
                    # Change ownership to 
                    os.chown(submission_dir, 1001, 1001)
                    # Also change ownership of parent dir
                    os.chmod(user_upload_path, 0o777)
                    # Change ownership to 
                    os.chown(user_upload_path, 1001, 1001)

                    with open(os.path.join(submission_dir, f'{submission_name}.md5sum'), 'w') as f:
                        # TODO make this more specific so that we only move over the files that are listed in the
                        # datasheet and the datasheet itself
                        
                        for root, dirs, files in os.walk(user_upload_path):
                            for filename in files:
                                if ".xlsx" in filename: # rename the datasheet to a standard format
                                    shutil.move(os.path.join(user_upload_path, filename), os.path.join(submission_dir, f"{submission_name}_datasheet.xlsx"))
                                    os.chmod(os.path.join(submission_dir, f"{submission_name}_datasheet.xlsx"), 0o777)
                                elif ".csv" in filename: # rename the datasheet to a standard format
                                    shutil.move(os.path.join(user_upload_path, filename), os.path.join(submission_dir, f"{submission_name}_datasheet.csv"))
                                    os.chmod(os.path.join(submission_dir, f"{submission_name}_datasheet.csv"), 0o777)
                                else:
                                    shutil.move(os.path.join(user_upload_path, filename), os.path.join(submission_dir, filename))
                                    os.chmod(os.path.join(submission_dir, filename), 0o777)
                                # capture the md5sum and add to file
                                # NB it was a lot of effor to get this working. The shell expansion was not working
                                # so we now do it file by file (even when using shell=True) and the fact that
                                # md5sum is an alias on the mac was also confusing things. So I advise you don't try to
                                # spend more time on this further.
                                try:
                                    f.write(subprocess.run(['md5sum', os.path.join(submission_dir, filename)],
                                                                 capture_output=True).stdout.decode("utf-8"))
                                except FileNotFoundError:
                                    f.write(
                                        subprocess.run(
                                            ['md5', '-r', os.path.join(submission_dir, filename)],
                                            capture_output=True
                                        ).stdout.decode("utf-8")
                                    )
                            break
                    os.chmod(os.path.join(submission_dir, f'{submission_name}.md5sum'), 0o777)
                    # TODO after we've done the moving, delete any files that might remain in the generic
                    # user directory

                    # 20221010 I am switiching off the for_analysis being false for the below sample types
                    # Determine if the Submission object for_analysis is True or False
                    # We will make the Submission for_analysis False if there are sample types of
                    # sponge, other_animal_host, seawater, sediment, epiphytic or other
                    sample_types = set(df['sample_type'].values)
                    for_analysis = True
                    # Start of turn off
                    # for sample_type in 'sponge other_animal_host seawater sediment epiphytic other'.split():
                    #     if sample_type in sample_types:
                    #         for_analysis = False
                    # End of turn off

                    # TODO allow a user other than the logged in user to be assigned to the submission.
                    # In the case that the user doesn't already exist, create the user and password credentials
                    # This will only be possible if admin. Also provide a dropdown menu for the admin of users.
                    # If a new user is created output the user credentials to the admin in the response message.
                    new_submission = Submission(
                        name=submission_name, web_local_dir_path=submission_dir, progress_status='submitted',
                        submitting_user_id=sp_user.id, number_samples=len(df.index),
                        framework_local_dir_path=submission_name, submission_date_time=dt_string,
                        for_analysis=for_analysis
                    )
                    db.session.add(new_submission)
                    db.session.commit()

                    # notify user or admin that submission was created
                    send_email(to_email=sp_user.email,
                               submission_status=new_submission.progress_status,
                               recipient_name=sp_user.name)

                    # TODO if for_analysis is False then report this in the message here
                    # Return a completed response
                    response = {
                        'error': False,
                        'message': '<strong class="text-success">UPLOAD COMPLETE</strong><br>'
                                   'Your submission status is: <strong>SUBMITTED</strong><br>'
                                   'The following Submission Object was created:<br><br>'
                                   f'<strong>submission.id:</strong> {new_submission.id}<br>'
                                   f'<strong>submission.name:</strong> {new_submission.name}<br>'
                                   f'<strong>submission.submitting_user_id:</strong> {sp_user.id}<br>'
                                   f'<strong>submission.submitting_user_name:</strong> {sp_user.name}<br>'
                                   f'<strong>submission.status:</strong> {new_submission.progress_status}<br>'
                                   f'<strong>submission.submission_date_time:</strong> '
                                   f'{new_submission.submission_date_time}<br><br>',
                        "complete_partial": "complete",
                        "response_type": "seq_file_upload",
                        "border_class": "border-success"
                    }

                    #TODO also put up a warning pop up or something to tell the user that they will not be able to
                    # run an analysis when they have uploaded their datasheet. This should be incorporated into the
                    # checks for the datasheet after it is uploaded.
                    if not for_analysis:
                        # If for_analysis is False then warn the user of this so that they will not be expecting
                        # ITS2 type profiles. It will likely be a good idea to include the for_analysis details
                        # on the homepage Submissions table.
                        response['message'] += 'At least one of your samples originates from a non-selective environment e.g. seawater<br>'
                        response['message'] += 'As such, no ITS2 type profiles will be predicted ' \
                                               'for this Submission<br>'
                        response['message'] += 'Your samples will be run through the SymPortal Quality Control ' \
                                               'pipeline producing a full set of sequence count tables ' \
                                               'and associated similarity outputs<br><br>'

                    response['message'] += 'Please check your homepage for status updates.<br>' \
                                           'This submission form has been reset.'

                    return jsonify(response)
                else:
                    # Then this is a partial completion of the upload and we will want to send back information
                    # that allows the updating of the staged area to show that the files have been uploaded.
                    # Something like an update to the status and a green outline to the cell.
                    response = {
                        'error': False,
                        "complete_partial": "partial",
                        "file_list": list(uploaded_filename_dict.keys()),
                        "response_type": "seq_file_upload"
                    }
                    return jsonify(response)


            except Exception as e:
                # Catch any unhandled errors and present on to the user with a full traceback of the error and
                # a 'please contact us' message
                tb = traceback.format_exc().replace("\n", "<br>")
                response = {
                    'error': True,
                    'message': '<strong class="text-danger">ERROR: an unhandled error has occurred when trying to '
                               'upload your sequencing files.</strong><br>'
                               'Please try again.<br>'
                               'If the error persists, please get in contact at:<br>'
                               f"{os.getenv('CONTACT_EMAIL_ADDRESS')}<br>"
                               f'The full backend traceback is:<br><br>{tb}',
                    "error_type": "unhandled_error",
                    "response_type": "seq_file_upload",
                    "border_class": "border-danger"
                }

                return jsonify(response)


def _load_data_sheet_df():
    # Load the datasheet as a df
    user_upload_path = os.path.join(app.config['UPLOAD_FOLDER'], current_user.name)
    datasheet_path = os.path.join(user_upload_path, request.form['datasheet_filename'])
    if datasheet_path.endswith('.xlsx'):
        df = pd.read_excel(
            io=datasheet_path, header=0, usecols='A:N', skiprows=[0])
    elif datasheet_path.endswith('.csv'):
        with open(datasheet_path, 'r') as f:
            datasheet_as_file = [line.rstrip() for line in f]
        if datasheet_as_file[0].split(',')[0] == 'sample_name':
            df = pd.read_csv(
                filepath_or_buffer=datasheet_path)
        else:
            df = pd.read_csv(
                filepath_or_buffer=datasheet_path, skiprows=[0])
    else:
        raise RuntimeError(f'Data sheet: {datasheet_path} is in an unrecognised format. '
                           f'Please ensure that it is either in .xlsx or .csv format.')
    return df, user_upload_path


@app.route('/_reset_submission', methods=['POST'])
@login_required
def _reset_submission():
    """
    This will be called when a user hits the reset button.
    Delete user upload dir. Recreate dir.
    """
    user_dir = os.path.join(app.config['UPLOAD_FOLDER'], current_user.name)
    # We want to delete the files that ae in the main user_dir, but not the sub directories
    # that will contain submitted files that are waiting for transfer to the framework server
    deleted_files = []
    for root, dirs, files in os.walk(user_dir):
        for fn in files:
            os.remove(os.path.join(user_dir, fn))
            deleted_files.append(fn)
        # Exit out before walking further down the tree
        break
    if not os.path.isdir(user_dir):
        os.makedirs(user_dir)
    return jsonify(deleted_files)
