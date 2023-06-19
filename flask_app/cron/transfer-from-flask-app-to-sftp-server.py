#!/usr/bin/env python3
import os
import sys
import time
import glob
import logging
import paramiko

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')


class SFTPClient:
    def __init__(self, hostname, username, password, local_path, remote_path):
        self.hostname = hostname
        self.username = username
        self.password = password
        self.client = None
        self.local_path = local_path
        self.remote_path = remote_path

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

        if not os.path.isdir(local_path):
            raise Exception("Invalid local directory path.")

        sftp = self.client.open_sftp()

        # Extract the username and submission name from the local_path
        username = os.path.basename(os.path.dirname(self.local_path))
        submission_name = os.path.basename(self.local_path)
        remote_submission_path = f'{self.remote_path}/{username}/{submission_name}'

        # We assume the user folder may exist
        try:
            sftp.mkdir(f'{self.remote_path}/{username}')
            logging.info(
                f'Remote submission user folder created: {self.remote_path}/{username}.')
        except IOError:
            logging.error(
                f'Remote submission path already exists: {self.remote_path}/{username}.')

        try:
            sftp.mkdir(remote_submission_path)
            logging.info(
                f'Remote submission path created: {remote_submission_path}.')
        except IOError:
            logging.error(
                f'Remote submission path already exists: {remote_submission_path}.')

        try:
            for item in os.listdir(self.local_path):
                # Copy file to remote
                sftp.put(os.path.join(self.local_path, item),
                         os.path.join(remote_submission_path, item))
                logging.info(f'Done with {item}!')
        finally:
            sftp.close()


def generate_lock_file(filepath):
    with open(filepath, 'w') as file:
        return


def remove_lock_file(filepath):
    if os.path.isfile(filepath):
        os.remove(filepath)
        logging.info(
            f'File the lock file {filepath} has been successfully removed.')
    else:
        logging.info(f'File {filepath} does not exist.')


def lock_file_exists(filepath):
    if os.path.exists(filepath):
        return True
    else:
        return False


def get_submissions_to_transfer(base_dir):
    # If folder exists and it is not empty
    if os.path.isdir(base_dir) and os.listdir(base_dir):
        return [directory for directory in
                glob.glob(os.path.join(base_dir, '*', '*')) if
                os.path.isdir(directory)]
    else:
        return list()


def select_submission(submissions):
    if len(submissions) == 0:
        sys.exit()
    return submissions[0]


if __name__ == '__main__':

    lock_file = f'/var/lock/{os.path.basename(__file__)}'

    # Only one cron job process can be running
    if lock_file_exists(lock_file):
        logging.info("Cron job process exists for the current script. Exiting.")
        sys.exit(0)

    # Generate the lock file to have only one cron running process
    generate_lock_file(lock_file)
    logging.info(f'Lock file generated. Current process ID: {os.getpid()}')

    submissions = get_submissions_to_transfer(base_dir='/app/sp_app/uploads')
    logging.info(f'Available submissions to transfer: {submissions}')

    logging.info(
        f'Establish connection with SFTP Server: {os.getenv("SYMPORTAL_SFTP_SERVER_CONTAINER")}.')
    sftp_client = SFTPClient(
        os.getenv('SYMPORTAL_SFTP_SERVER_CONTAINER'),
        os.getenv('SFTP_USERNAME'),
        os.getenv('SFTP_PASSWORD')
    )
    try:
        # Connect to the SFTP server
        sftp_client.connect()
        sftp_client.copy_submission(select_submission(submissions),
                                    os.getenv("SFTP_HOME"))
    finally:
        sftp_client.disconnect()
        remove_lock_file(lock_file)
