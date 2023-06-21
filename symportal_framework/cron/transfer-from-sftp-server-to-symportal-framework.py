import os
import sys
import glob
import django
import shutil
import hashlib
import logging
import paramiko

# Initialize Django
django.setup()
# Import from installed Apps
from dbApp.models import Submission

# Configure logging
logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class SFTPClient:
    def __init__(self, hostname, username, password, submission):
        self.hostname = hostname
        self.username = username
        self.password = password
        self.client = None
        self.submission = submission
        self.local_path = os.path.join(
            '/mnt',
            self.submission.submitting_user.name,
            self.submission.name)
        self.remote_path = os.path.join(
            os.getenv('SFTP_HOME'),
            self.submission.submitting_user.name,
            self.submission.name)

    def connect(self):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(self.hostname, username=self.username,
                            password=self.password)

    def disconnect(self):
        if self.client is not None:
            self.client.close()

    def copy_submission(self):
        if self.client is None:
            raise Exception("Not connected to SFTP server.")

        sftp = self.client.open_sftp()

        # Create the local directory if it doesn't exist
        if not os.path.exists(self.local_path):
            os.makedirs(self.local_path)
            logging.info(
                f'Local submission path created: {self.local_path}.')

        sftp.chdir(self.remote_path)

        try:
            # Iterate over the files and folders in the remote directory
            for item in sftp.listdir():
                local_item_path = os.path.join(self.local_path, item)
                # Copy the file to the local directory
                sftp.get(item, local_item_path)
                logging.info(f'Done with {item}.')
        finally:
            sftp.close()

    def _create_md5sum_dictionary(self):
        md5sum_dict = {}

        try:
            file_paths = glob.glob(os.path.join(self.local_path, '*.md5sum'))
            if len(file_paths) == 0:
                raise FileNotFoundError(
                    f'No md5sum files found in the specified folder: {self.local_path}.')

            # Assuming there is only one md5sum file in the folder
            file_path = file_paths[0]

            with open(file_path, 'r') as file:
                md5sum_dict = {os.path.basename(line.strip().split('  ')[1]):
                                   line.strip().split('  ')[0] for line in file}
        except FileNotFoundError as e:
            logging.error(e)
        except Exception as e:
            print(f'An error occurred while processing the file: {e}.')

        return md5sum_dict

    def md5sum_check(self):
        md5sum_dict = self._create_md5sum_dictionary()

        for filename, existing_checksum in md5sum_dict.items():
            local_file_path = os.path.join(self.local_path, filename)

            # Calculate the MD5 checksum of the local file
            md5_hash = hashlib.md5()
            with open(local_file_path, 'rb') as local_file:
                for chunk in iter(lambda: local_file.read(4096), b''):
                    md5_hash.update(chunk)

            local_checksum = md5_hash.hexdigest()

            # Compare the local checksum with the existing checksum
            if local_checksum == existing_checksum:
                logging.info(
                    f'The MD5 checksum of {filename} matches the existing checksum.')
            else:
                error_message = f'The MD5 checksum of {filename} does not match the existing checksum.'
                logging.error(error_message)
                raise Exception(error_message)

        logging.info('The MD5 checksum completed.')
        return True

    def update_submission_status(self):
        self.submission.progress_status = 'transfer_to_framework_server_complete'
        self.submission.save()
        logging.info(
            f'The submission status has been updated to {self.submission.progress_status}.')

    def delete_remote_submission(self):
        sftp = self.client.open_sftp()
        try:
            for file in sftp.listdir(self.remote_path):
                sftp.remove(os.path.join(self.remote_path, file))
            sftp.rmdir(self.remote_path)
            logging.info(
                f'Directory {self.remote_path} and its contents were '
                f'successfully removed.')
        except FileNotFoundError:
            logging.warning(f'Directory {self.remote_path} does not exist.')
        except Exception as e:
            logging.error(
                f'An error occurred while removing directory {self.remote_path}: {e}')


def generate_lock_file(filepath):
    with open(filepath, 'w') as file:
        return


def remove_lock_file(filepath):
    if os.path.isfile(filepath):
        os.remove(filepath)
        logging.info(
            f'The lock file {filepath} has been successfully removed.')
    else:
        logging.info(f'File {filepath} does not exist.')


def lock_file_exists(filepath):
    if os.path.exists(filepath):
        return True
    else:
        return False


def get_submissions_to_transfer():
    # Return QuerySet
    return Submission.objects.filter(
        progress_status='transfer_to_sftp_server_complete',
        error_has_occured=False)


def select_submission(submissions):
    if len(submissions) == 0:
        logging.warning('There are no available submissions.')
        sys.exit(1)
    return submissions[0]


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
            get_submissions_to_transfer()
        )

        logging.info(
            f'Establish connection with SFTP Server: {os.getenv("SYMPORTAL_DATABASE_CONTAINER")}.')
        sftp_client = SFTPClient(
            hostname=os.getenv('SYMPORTAL_SFTP_SERVER_CONTAINER'),
            username=os.getenv('SFTP_USERNAME'),
            password=os.getenv('SFTP_PASSWORD'),
            submission=submission)

        try:
            # Connect to the SFTP server
            sftp_client.connect()
            # Process submission
            sftp_client.copy_submission()
            if sftp_client.md5sum_check():
                sftp_client.delete_remote_submission()
                sftp_client.update_submission_status()
        finally:
            sftp_client.disconnect()

    finally:
        remove_lock_file(lock_file)
