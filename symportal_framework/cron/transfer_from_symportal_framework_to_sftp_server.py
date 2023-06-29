#!/usr/bin/env python3
import hashlib
import os
import sys
import logging
import zipfile
import paramiko
# Lock file logic for one existing cron job
from transfer_from_sftp_server_to_symportal_framework import generate_lock_file, \
    lock_file_exists, remove_lock_file
# For submission selections
from transfer_from_sftp_server_to_symportal_framework import \
    get_submissions_to_transfer, select_submission

# Configure logging
logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class SFTPClient:
    def __init__(self, hostname, username, password, local_path, remote_path):
        self.hostname = hostname
        self.username = username
        self.password = password
        self.client = None
        self.local_path = local_path
        self.remote_path = remote_path
        self.remote_output_path = \
            os.path.join(
                self.remote_path,
                self.local_path.split('/')[-2],
                self.local_path.split('/')[-1])

    def connect(self):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(self.hostname, username=self.username,
                            password=self.password)

    def disconnect(self):
        if self.client is not None:
            self.client.close()

    def create_remote_dirs(self):
        folders = self.remote_output_path.split('/')
        current_path = ''

        sftp = self.client.open_sftp()

        try:
            for folder in folders:
                if folder:
                    current_path += '/' + folder
                    try:
                        sftp.chdir(current_path)
                    except IOError:
                        try:
                            sftp.mkdir(current_path)
                        except IOError as e:
                            # If the folder creation failed, raise an exception or handle the error
                            logging.error(
                                f'Failed to create folder: {current_path}. '
                                f'Error: {str(e)}')
            logging.info(f'Remote submission path exists or were created: '
                         f'{self.remote_output_path}')
        finally:
            sftp.close()

    def compress_output(self, submission):
        output_path = os.path.join(self.local_path, submission.name) + '.zip'
        folder_path = self.local_path
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    zipf.write(file_path,
                               os.path.relpath(file_path, folder_path))
        logging.info(
            f'Folder {folder_path} zipped to {output_path} successfully.')

    def copy_analysis_output(self):
        if self.client is None:
            raise Exception('Not connected to SFTP server.')

        if not os.path.isdir(self.local_path):
            raise Exception(
                f'Invalid local directory path : {self.local_path}.')

        sftp = self.client.open_sftp()

        try:
            sftp.put(os.path.join(self.local_path, submission.name) + '.zip',
                     os.path.join(self.remote_output_path,
                                  submission.name) + '.zip')
            sftp.put(os.path.join(self.local_path, submission.name) + '.md5sum',
                     os.path.join(self.remote_output_path,
                                  submission.name) + '.md5sum')
            logging.info(f'Output {submission.name}.zip archive was '
                         f'successfully transferred to remote '
                         f'SFTP Server: {self.remote_output_path}')
        finally:
            sftp.close()


def calculate_checksum(file_path, algorithm='md5'):
    hash_algorithm = hashlib.new(algorithm)

    with open(file_path, 'rb') as file:
        for chunk in iter(lambda: file.read(4096), b''):
            hash_algorithm.update(chunk)


def write_checksum_to_file(file_path, checksum):
    with open(file_path, 'w') as file:
        file.write(checksum)


def update_submission_status(submission):
    submission.progress_status = 'transfer_from_framework_to_sftp_server_complete'
    submission.save()
    logging.info(
        f'The submission status has been updated to {submission.progress_status}.')


if __name__ == '__main__':

    lock_file = f'/var/lock/{os.path.basename(__file__)}.lock'

    # Only one cron job process can be running
    if lock_file_exists(lock_file):
        logging.info("Cron job process exists for the current script. Exiting.")
        sys.exit(1)

    # Main try block that always finishes with deleting of lock file
    try:
        # Generate the lock file to have only one cron running process
        generate_lock_file(lock_file)
        logging.info(f'Lock file generated. Current process ID: {os.getpid()}')

        submission = select_submission(
            get_submissions_to_transfer(
                status='framework_output_complete'))

        logging.info(
            f'Establish connection with SFTP Server: {os.getenv("SYMPORTAL_DATABASE_CONTAINER")}.')
        sftp_client = SFTPClient(
            hostname=os.getenv('SYMPORTAL_SFTP_SERVER_CONTAINER'),
            username=os.getenv('SFTP_USERNAME'),
            password=os.getenv('SFTP_PASSWORD'),
            local_path=submission.framework_results_dir_path,
            remote_path=os.path.join(os.getenv('SFTP_HOME'), 'outputs'))

        try:
            # Connect to the SFTP server
            sftp_client.connect()
            # Process submission
            sftp_client.create_remote_dirs()
            sftp_client.compress_output(submission)
            calculate_checksum(file_path=os.path.join(sftp_client.remote_output_path, submission.name) + '.zip')
            write_checksum_to_file(file_path=os.path.join(sftp_client.remote_output_path, submission.name) + '.md5sum')
            sftp_client.copy_analysis_output()
            update_submission_status(submission)
        finally:
            sftp_client.disconnect()

    finally:
        remove_lock_file(lock_file)
