import os
import sys
import glob
import django
import hashlib
import logging
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
                self.local_path.split()[-1],
                self.local_path.split()[-2])

    def connect(self):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(self.hostname, username=self.username,
                            password=self.password)

    def disconnect(self):
        if self.client is not None:
            self.client.close()

    def copy_analysis_output(self):
        if self.client is None:
            raise Exception("Not connected to SFTP server.")

        if not os.path.isdir(self.local_path):
            raise Exception(
                f'Invalid local directory path : {self.local_path}.')

        sftp = self.client.open_sftp()

        try:
            # copy logic
            for item in os.listdir(self.local_path):
                item_local_path = os.path.join(self.local_path, item)
                item_remote_path = os.path.join(self.remote_output_path, item)

                # If it's a file, copy it to the remote server
                if os.path.isfile(item_local_path):
                    sftp.put(item_local_path, item_remote_path)
                    logging.info(f'Done with {item}.')
                # If it's a directory, recursively copy its contents
                elif os.path.isdir(item_local_path):
                    sftp.mkdir(item_remote_path)
                    self.copy_analysis_output()
        finally:
            sftp.close()


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
            sftp_client.copy_analysis_output()
        finally:
            pass

    finally:
        remove_lock_file(lock_file)
