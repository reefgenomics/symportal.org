#!/usr/bin/env python3
"""
20220628
We are now running live from the Zygote postgres db.
I'm not sure why weren't doing this sooner. The connection speed seems fine.
This means that we can get rid of all of the code to do with uploading the bak file
dumping the db, creating a new db and retoring a db which is great.
Because we are now running directly from the zygote db,
we have attached the password info to the symportal_database user object
so it is now no longer necessary to have the sqlite3 database seperately for
password management. As such the entire syny_db.py scipt is now obsolete.

Old

We want to automate the process of getting an SP output up and displayed on the symportal.org website

We will coordinate this from our local machine as this doesn't have a fixed IP whilst the servers do.
Let's have a flag that we have to implement when doing a --print_output_types that will automatically ask for
the input of the the information we need including username and studyname. a .bak will be output as well as
an accompanying json file that will include username and study name (this should be the same as dataset name) 
info as well as the path to the .bak It should also contain the uid of the dataset. This can be output to the output dir.

From Local: Provide the host and directory where the output data is.
Provide the directory where this should be going on the remote linode server.
Pull down the data to local and process in a new empty direcotry that matches the name
(check that this is empty first)
After successful processing, check that the linode directory doesn't already exist
If not, then send over the processed data directory.
Modify the json sp .json
Also send over the .bak to a postgres database directory.
Also send over the json sp.json
Fire the script to create a new user in the sqlite db.
Then Fire the script to dropdb, createdb and loaddb.
Then fire script to sync the .bak to the sqlite.
# At this point the symportal.org should be ready to go.
Now pull back down to local.
pull down the app.db
pg_dump out to a .bak, drop, create, restore on local.
# Now local should be good to go.


On Zygote:
This will be fired either from within SymPortal itself or manually.
Arguments will be the id of the dataset, the id of the data analysis, the username to be created
the Study name to be populated.
Out put a .bak to to the dbBackup directory with todays date, and the time appened.
Produce a read me that informs that this was create progromatically and detail the
output that it was produced for, i.e. the data analysis and the data set sample output.
Then try to fire the script on local.

20200526 it would be good to be able to do an update to. I.e. where the study already exists
Maybe we can build this in as the default. If the user exsits then we check for the study
If the study exists then we should check to see what the current dataset id matches the new

We can pass in an update key word that will mean that if the directory already exists
We can rename it as *_archive_date and then continue with the pull down. We could do the same
for the put to the remote server. It is probably easiest if we work with comma delimited, paths to outputs folders
and then we can get lists of users and datasets to add etc. But this will be quite a bit of work.
"""
import sys
import argparse
from getpass import getpass
import paramiko
import os
import json
import ntpath
import subprocess
import shutil
from zipfile import ZipFile
from colorama import Fore, Style
import datetime

class AutomateSync:
    def __init__(self):
        # General parameters
        self.parser = argparse.ArgumentParser()
        self._define_args()
        self.args = self.parser.parse_args()
        
        # List of the data output directories we will be working with
        self.remote_sp_output_paths = self.args.remote_sp_output_paths.split(',')
        # List of the study_output_info.json objects that we will be working with
        self.remote_sp_json_info_paths = [os.path.join(_, 'study_output_info.json') for _ in self.remote_sp_output_paths]
        
        # A list of the json info objects
        self.json_info_object_list = []

        # This is a convenience list that is created from joining the local data dir
        # with the study name in question.
        self.local_data_dirs = []
        self.remote_sp_host_pass = getpass('Password for remote SymPortal_framework server: ')
        
        # Parameters for the web server
        if self.args.remote_web_connection_type == 'IP':
            self.remote_web_password = getpass('Password for remote web server: ')
        else:
            self.pem_file_path = self.args.pem_file_path
        
        # Initial SSH and sftp clients
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.load_system_host_keys()
        self.ssh_client.connect(hostname=self.args.remote_sp_host_id, username=self.args.remote_sp_host_user, password=self.remote_sp_host_pass)
        # Open sftp client
        self.sftp_client = self.ssh_client.open_sftp()

    def start_sync(self):
        self._read_json_info_from_sp_server()
        
        self._download_and_prep_data_if_necessary()
        
        self._connect_to_remote_web_server()
        
        self._upload_to_web_server()
        
        # At this point, the data is all in place and we should be all setup to
        # test the local server.
        
    def _ask_continue_sync(self):
        while True:
            continue_text = input('Continue with synchronisation? [y/n]: ')
            if continue_text == 'y':
                return True
            elif continue_text == 'n':
                return False
            else:
                print('Unrecognised response. Please answer y or n.')

    def _read_json_info_from_sp_server(self):
        # first open up the info json file
        for remote_sp_json_info_path in self.remote_sp_json_info_paths:
            print('Reading the ouput json info file:')
            with self.sftp_client.open(remote_sp_json_info_path, 'r') as f:
                json_info = json.load(f)
            print('JSON info file successfully read:')
            for k, v in json_info.items():
                print(f'{k}: {v}')
            self.json_info_object_list.append(json_info)

    def _download_and_prep_data_if_necessary(self):
        for json_info, remote_sp_output_path in zip(self.json_info_object_list, self.remote_sp_output_paths):
            # check to see if a directory already exists for the study in question
            local_data_dir = os.path.join(self.args.local_symportal_data_directory, json_info["study"])
            self.local_data_dirs.append(local_data_dir)
            if os.path.exists(local_data_dir):
                print(f"{Fore.RED}WARNING: Local directory {local_data_dir} already exists.{Style.RESET_ALL}")
                print("This directory will not be overwritten.")
                print("If synchronisation continues, this directory will be used as it is.")
                print("No further processing will be conducted on it.")
                if self._ask_continue_sync():
                    # Then we can skip the pull down and processing
                    pass
                else:
                    sys.exit(1)
            else:
                # We need to pull down the data and then process it
                os.makedirs(local_data_dir)
                print(f'Pulling down data from {remote_sp_output_path}')
                self._pull_down_data(remote_sp_output_path=remote_sp_output_path, local_data_dir=local_data_dir)
                print('Processing data for upload')
                self._process_sp_output_data(local_data_dir=local_data_dir, json_info=json_info)

    def _connect_to_remote_web_server(self):
        self.ssh_client.close()
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.load_system_host_keys()
        if self.args.remote_web_connection_type == 'IP':
            # Working with linode instance
            self.ssh_client.connect(hostname=self.args.remote_web_host, username=self.args.remote_web_user, password=self.remote_web_password, timeout=5.0)
        else:
            # Working with the amazon aws ec2 instance
            self.ssh_client.connect(hostname=self.args.remote_web_host, username=self.args.remote_web_user, key_filename=self.pem_file_path, timeout=5.0)
        
        # Open sftp client
        self.sftp_client = self.ssh_client.open_sftp()
    
    def _upload_to_web_server(self):
        # Send the data directories up to the remote web server
        # send the sp_json up to the server as well
        for json_info, local_data_dir in zip(self.json_info_object_list, self.local_data_dirs):
            # Check to see if the data directory exists
            if json_info["study"] in self.sftp_client.listdir(self.args.remote_web_symportal_data_directory):
                print(f'{Fore.RED}WARNING: Directory {json_info["study"]} already exists in the remote web server data directory.{Style.RESET_ALL}')
                print('We will not upload anything additional to this directory.')
                if self._ask_continue_sync():
                    # Then we can skip the data upload
                    pass
                else:
                    sys.exit(1)
            else:
                remote_web_data_dir = os.path.join(self.args.remote_web_symportal_data_directory, json_info["study"])
                self.sftp_client.mkdir(remote_web_data_dir)
                self._put_all(remote=remote_web_data_dir, local=local_data_dir)
    
    def _process_sp_output_data(self, local_data_dir, json_info):
        """
        Get the data in the format required for the symportal.org server
        """
        # At this point we have the datafiles pulled down.
        # Now its time to process them
        # 1 - mv the html/study.js file out from in the html directory.
        shutil.move(os.path.join(local_data_dir, 'html', 'study_data.js'), os.path.join(local_data_dir, 'study_data.js'))
        # 1b if this is a loading output (i.e. no analysis) then delete the non_sym_and_size_violation_sequences
        # directory so that we don't take up valuable space
        if os.path.exists(os.path.join(local_data_dir, 'non_sym_and_size_violation_sequences')):
            shutil.rmtree(os.path.join(local_data_dir, 'non_sym_and_size_violation_sequences'))
        # 2 - zip into one file that we will temporarily hold in the base data directory
        # 3 - at the same time create an idividual zip of the file
        # https://thispointer.com/python-how-to-create-a-zip-archive-from-multiple-files-or-directory/
        master_zip_path = os.path.join(local_data_dir, f'{json_info["study"]}.zip')
        with ZipFile(master_zip_path, 'w') as zipObj:
            # Iterate over all the files in directory
            for folderName, subfolders, filenames in os.walk(local_data_dir):
                for filename in filenames:
                    #create complete filepath of file in directory
                    filePath = os.path.join(folderName, filename)
                    # check that it is not the .zip itself
                    if filePath == master_zip_path:
                        continue
                    # Add file to zip
                    # https://stackoverflow.com/questions/27991745/zip-file-and-avoid-directory-structure
                    zipObj.write(filePath, arcname=os.path.relpath(filePath, start=self.args.local_symportal_data_directory))
                    # Now zip the file individually unless it is the study_data.js file
                    if not 'study_data.js' in filePath:
                        with ZipFile(f'{filePath}.zip', 'w') as sub_zip_obj:
                            # https://stackoverflow.com/questions/27991745/zip-file-and-avoid-directory-structure
                            sub_zip_obj.write(filePath, arcname=os.path.relpath(filePath, start=folderName))
                        # and then remove that file
                        os.remove(filePath)

    def _pull_down_data(self, remote_sp_output_path, local_data_dir):
        """
        Grab the data from the SymPortal output directory.
        This is much more complicated than it seems, there seems to be no simple way to recursively transfer files.
        I have written the function _get_all, but it is very slow.
        Alternatively we can try scp but we will have to use sshpass to use a password on the commandline
        and so that we don't have this written out on our system we should write the password out to a temp file
        Turns out that this prevents us from getting an stdout output
        The alternative is to set up an ssh/rsa key pair and then use this with scp, but there
        is no way to pass in the passphrase for the key pairs and so the keys would have to be used unencrypted
        I don't want to do that. So we're back to square one, that is the slow get all.
        """
        self._get_all(remote=remote_sp_output_path, local=local_data_dir)
        
    def _put_all(self, remote, local):
        remote_contents = self.sftp_client.listdir(remote)
        for put_file in os.listdir(local):
            if '.' in put_file:
                if 'DS_Store' in put_file:
                    continue
                if put_file in remote_contents:
                    print(f'{os.path.join(local, put_file)} already exists')
                else:
                    print(f'putting: {os.path.join(local, put_file)}')
                    return_obj = self.sftp_client.put(os.path.join(local, put_file), os.path.join(remote, put_file))

            else:
                # Then this is a directory and we need to drop into it after creating it
                if put_file not in remote_contents:
                    self.sftp_client.mkdir(os.path.join(remote, put_file))
                self._put_all(remote=os.path.join(remote, put_file), local=os.path.join(local, put_file))
        return

    def _get_all(self, remote, local):
        for get_file in self.sftp_client.listdir(remote):
            if '.' in get_file:
                if os.path.exists(os.path.join(local, get_file)):
                    print(f'{os.path.join(local, get_file)} already exists')
                else:
                    print(f'getting: {os.path.join(remote, get_file)}')
                    self.sftp_client.get(os.path.join(remote, get_file), os.path.join(local, get_file))
            else:
                # Then this is a directory and we need to drop into it after creating it
                # Skip it if it is the non_sym_and_size_violation_sequences dir
                if get_file == 'non_sym_and_size_violation_sequences':
                    continue
                os.makedirs(os.path.join(local, get_file), exist_ok=True)
                self._get_all(remote=os.path.join(remote, get_file), local=os.path.join(local, get_file))
        return
            
    def _define_args(self):
        # Parameter for local machine
        self.parser.add_argument(
            '--local_symportal_data_directory', 
            help='The base directory where the individual study directories are held on the local machine', 
            default='/Users/benjaminhume/Documents/symportal.org/sp_app/explorer_data')
        self.parser.add_argument('--pem_file_path', help='Full path to the .pem file to connect to the AWS instance', default=None),
        
        # Parameters for symportal_framework_server
        self.parser.add_argument(
            '--remote_sp_output_paths', 
            type=str, 
            help='The path(s) to the base output directory of the SymPortal output on the remote SymPortal server. For multiple outputs, this can be comma separated.', 
            required=True
            )
        self.parser.add_argument(
            '--remote_sp_host_id', 
            type=str, 
            help='The IP of the server that you want to grab the SymPortal output from [defaut=134.34.126.43;zygote]', 
            default='134.34.126.43'
            )
        self.parser.add_argument(
            '--remote_sp_host_user', 
            type=str, 
            help='The useraccount for ssh to the remote SymPortal server [default=humebc]', 
            default='humebc'
            )

        # Symportal.org webpage server
        self.parser.add_argument('--remote_web_connection_type', help='Either IP or PEM.', default='IP'),
        self.parser.add_argument('--remote_web_bak_dir', help="Path to the directory on the web server where the .bak file should be deposited", default="/home/humebc/symportal.org/symportal_database_versions")
        self.parser.add_argument('--remote_web_sync_script_path', help="Full path to the syncronization script to run on the web server", default="/home/humebc/symportal.org/sync_db.py")
        self.parser.add_argument(
            '--remote_web_host', 
            type=str, 
            help='The IP of the server to upload data to [defaut=172.104.241.93;linode]', 
            default='172.104.241.93'
            )
        self.parser.add_argument(
            '--remote_web_user', 
            type=str, 
            help='The useraccount for ssh to the remote symportal.org server [default=humebc]', 
            default='humebc'
            )
        self.parser.add_argument('--pem_path', help='The path to the .pem file if sshing to an AWS server')
        self.parser.add_argument(
            '--remote_web_symportal_data_directory', 
            help='The base directory where the individual study directories are held on the web machine', 
            default='/home/humebc/symportal.org/sp_app/explorer_data')
        
AutomateSync().start_sync()