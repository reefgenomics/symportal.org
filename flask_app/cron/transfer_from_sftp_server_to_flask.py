import os
import logging
import paramiko

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

    def connect(self):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(self.hostname, username=self.username,
                            password=self.password)

    def disconnect(self):
        if self.client is not None:
            self.client.close()


def get_submissions_to_transfer(status):
    # Return QuerySet
    return Submission.objects.filter(
        progress_status=status,
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
            get_submissions_to_transfer(
                status='transfer_from_framework_to_sftp_server_complete'))

        logging.info(
            f'Establish connection with SFTP Server: {os.getenv("SYMPORTAL_DATABASE_CONTAINER")}.')
        sftp_client = SFTPClient(
            hostname=os.getenv('SYMPORTAL_SFTP_SERVER_CONTAINER'),
            username=os.getenv('SFTP_USERNAME'),
            password=os.getenv('SFTP_PASSWORD'),
            local_path=submission.framework_results_dir_path,
            remote_path=os.path.join(
                os.getenv('SFTP_HOME'),
                'outputs',
                submission.framework_results_dir_path('/')[-1],
                submission.framework_results_dir_path('/')[-2])
        )

        try:
            # Connect to the SFTP server
            sftp_client.connect()
            # Process submission
            sftp_client.copy_analysis_output()
            update_submission_status(submission)
        finally:
            pass

    finally:
        remove_lock_file(lock_file)
