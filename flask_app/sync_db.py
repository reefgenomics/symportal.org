#!/usr/bin/env python3
"""
20220628
We are now connecting remotely to the zygote postgres db so we no longer need to do the syncing

Old
This script will be run when we transfer a datbase version from the remote symportal instance
to the symportal.org server. This transfer will always be in one directrion. From the symportal
instance, to the symportal server. This transfer will most often occur when we are adding a new study and or user
to the SymPortal.org collection of studies.
The first thing to do will be to drop the current database, create a newone and then restore with the new back.
I think we should keep a total of 3 .bak files. We can keep the original names, but append a 0, 1 or 2 to them
so that the 0 is the newest, the 1 is the next newest etc. If a 2 exists at the point of transfer, we will delete this.
Once the new database has been restored from the .bak, we will sync the database using the published_articles_sp
that will also have been sent up. I think it will be a good idea to have a common part of the name between the 
published articles sp json and the database. I think date and time are probably a good idea. Like the .bak, we
can keep some versions of the published articles sp json.

User objects and Study objects will only every be added to the
database during the sync performed by this script that will only every be run on a symportal.org
server. As such every time a sync happens, all the User and Study objects will be recreated 
using this script. The list of Study and User instances that should exist will be stored in the
published_articles_sp.json. Each of the User objects in the symportal_database will have an
associated User object in the symportal.org database. Currently the symportal.org database
also contains a DataSet object but we will be getting rid of this. The only reason we keep a
'copy' of the User object in the symportal.org database is because the user passwords are
stored there and the users can change these at any time.
When the syncing happens, the User objects will be created first and these will look for 
associated user objects in the symportal.org database. If it can't find an associated User
it will create one (after checking that there are no superflous users in the database).
Next it will create Study objects that will be linked to datasetsample objects. Finally, the 
Study objects will be linked to the datasetsample objects.

Once this is completed, the symportal.org code will be able to work from the newly synced db.
"""

from sp_app import db
# The User is the class from the symportal.org database, i.e. the one that houses the passwords
# The SPUser is the User class from the symportal_database
from sp_app.models import SPDataSet, DataSetSample, Study, SPUser, User, ReferenceSequence, DataSetSampleSequencePM, DataSetSampleSequence, Study__DataSetSample
import sys
from sqlalchemy.orm.exc import NoResultFound
from datetime import datetime
import json
import pickle
import os
import subprocess
from time import time
import argparse
import ntpath
import shutil
import hashlib

class DBSync:
    def __init__(self):
        self.parser = argparse.ArgumentParser()
        self._define_args()
        self.args = self.parser.parse_args()
        self.bak_archive_dir = self.args.bak_archive_dir
        self.path_to_new_bak = self.args.path_to_new_bak
        self.psql_user = self.args.psql_user 
        self.prompt = self.args.no_prompt

    def _define_args(self):
        self.parser.add_argument('-y', '--no_prompt', help="Do not prompt before making commits", action='store_false', default=True)     

    def sync(self):
        self._verfiy_and_create_users()
        print('Sync complete.')

    def _archive_bak(self):
        """
        In the symportal_database_archive_dir there should be up to three
        files that have been prefixed eith 0, 1, 2 depending on which order they were up load.
        Here we want to add the bak file to these archives and update the namings accordingly.
        """
        bak_file_name = ntpath.basename(self.path_to_new_bak)
        self.new_archived_bak_path = os.path.join(self.bak_archive_dir, f'0_{bak_file_name}')

        if not os.path.isfile(self.new_archived_bak_path):
            if os.path.isfile(os.path.join(self.bak_archive_dir, bak_file_name)):
                pass
            else:
                shutil.move(self.path_to_new_bak, os.path.join(self.bak_archive_dir, bak_file_name))
            # Then update the namings
            # We will need to grab the names and then update outside of for loop
            # below to prevent renaming 1 -- > 2 before deleteing the old 2.
            one_file_name_bak = None
            zero_file_name_bak = None
            for bak_archive_file in os.listdir(self.bak_archive_dir):
                if bak_archive_file.startswith('2_') and bak_archive_file.endswith('.bak'):
                    # Then this is the oldest file and it needs to be removed
                    os.remove(os.path.join(self.bak_archive_dir, bak_archive_file))
                elif bak_archive_file.startswith('1_') and bak_archive_file.endswith('.bak'):
                    one_file_name_bak = bak_archive_file
                elif bak_archive_file.startswith('0_') and bak_archive_file.endswith('.bak'):
                    zero_file_name_bak = bak_archive_file
            
            # now do the renaming.
            if one_file_name_bak is not None:
                shutil.move(os.path.join(self.bak_archive_dir, one_file_name_bak), os.path.join(self.bak_archive_dir, one_file_name_bak.replace('1_', '2_')))
            if zero_file_name_bak is not None:
                shutil.move(os.path.join(self.bak_archive_dir, zero_file_name_bak), os.path.join(self.bak_archive_dir, zero_file_name_bak.replace('0_', '1_'))) 
            # finally, rename the new json file
            shutil.move(os.path.join(self.bak_archive_dir, bak_file_name), os.path.join(self.bak_archive_dir, f'0_{bak_file_name}'))
    
    def _restore_from_bak(self):
        # Drop the db
        print('Dropping db')
        result = subprocess.run(['dropdb', '-U', self.psql_user, '-w', 'symportal_database'], check=True)
        # Remake the db
        print('Creating db')
        result = subprocess.run(['createdb', '-U', self.psql_user, '-O', self.psql_user, '-w', 'symportal_database'], check=True)
        # Restore the db from the .bak
        print('Restoring db. This make take some time...')
        result = subprocess.run(['pg_restore', '-U', self.psql_user, '-w', '-d', 'symportal_database', '-Fc', self.new_archived_bak_path])
        print('Db successfuly restored')

    def _verfiy_and_create_users(self):
        """
        For every User object in the symportal_database check to see if there is a User with exactly
        the same name in the symportal_org databaes.
        If there is, great.
        If not, create a new user.
        Then we will also do the reciprocal check. For every user in the symportal_org database
        check to see if there is a corresponding User in the symportal_database.
        If there is, great.
        If not, then warn the user. Collect all such mismatches and print to stdout. We will not delete
        users from the symportal_org database for obvious reasons.
        """
        users_to_create = []
        for sp_user in SPUser.query.all():
            try:
                match = User.query.filter(User.username==sp_user.name).one()
            except NoResultFound:
                print(f"Match for symportal_database User '{sp_user.name}' was not found")
                print('Creating a new non-admin User in the symportal_org database')
                new_user = User(username=sp_user.name)
                try:
                    study_name_to_hash_from = sp_user.studies.first().name
                except AttributeError:
                    study_name_to_hash_from = "first_study_281723"
                # Set the initial password for the user
                sum_numbers_from_study_name_as_str = str(sum([int(i) for i in list(study_name_to_hash_from) if i.isdigit()]))
                to_hash = f'{sp_user.name}{sum_numbers_from_study_name_as_str}'.encode('utf-8')
                u_pass = hashlib.md5(to_hash).hexdigest()
                new_user.set_password(u_pass)
                db.session.add(new_user)
                users_to_create.append((new_user, u_pass))
        # At this point we have created all of the required
        if users_to_create:
            # If there are objects to create then verify with the user that they should be
            # created.
            print("The following User objects were not found in the symportal_org database:")
            for u in users_to_create:
                print(f"\tnew user {u[0]}: {u[1]}")
            if self.prompt:
                commit_y_n = input("These objects will be created. Continue with commit? (y/n):")
                if commit_y_n == 'y':
                    print('Creating new objects')
                    db.session.commit()
                else:
                    raise SystemExit('No new User objects have been created. Exiting')
            else:
                print('Creating new objects')
                db.session.commit()
        else:
            # There are no new objects to create
            print("All symportal.org User objects already exist")
        
        print('\nChecking for redundant symportal.org User objects')
        redundant_users = []
        for so_user in User.query.all():
            try:
                match = SPUser.query.filter(SPUser.name==so_user.username).one()
            except NoResultFound:
                redundant_users.append(so_user)
        if redundant_users:
            print('The following symportal.org User objects were found that did not exist in the symportal_datase:')
            for so_user in redundant_users:
                print(f'\t{so_user.username}')
            print('These redundant objects reamin untouched')
        else:
            print('No redundant symportal.org User objects were found')
        

    @staticmethod
    def md5sum(filename):
        with open(filename, mode='rb') as f:
            d = hashlib.md5()
            for buf in iter(partial(f.read, 128), b''):
                d.update(buf)
        return d.hexdigest()

sync = DBSync()
sync.sync()