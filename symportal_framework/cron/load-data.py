import os
import sys
import django
import logging
from datetime import datetime

# Initialize Django
django.setup()
# Import from installed Apps
import main
from dbApp.models import Submission

# Configure logging
logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class DataLoader:
    def __int__(self, args):
        self.workflow_manager = main.SymPortalWorkFlowManager(args)

    def update_submission(self, submission):
        # Assign the associated DataSet and Study objects
        submission.associated_dataset = \
            self.workflow_manager.data_loading_object.dataset_object
        submission.associated_study = \
            self.workflow_manager.data_loading_object.study
        submission.loading_complete_date_time = datetime.utcnow().strftime(
            '%Y%m%dT%H%M%S')
        if submission.for_analysis:
            submission.progress_status = 'framework_loading_complete'
        else:
            submission.framework_results_dir_path = \
                self.workflow_manager.data_loading_object.output_directory
            submission.progress_status = 'framework_output_complete'
        submission.save()
        logging.info(
            f'The status of submission {submission.name} has been changed to {submission.progress_status}.')


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


def check_incomplete_submissions():
    in_progress = Submission.objects.filter(
        progress_status='transfer_to_framework_server_complete',
        loading_started_date_time=None)
    if in_progress:
        logging.warning(
            'Incomplete loading detected:\n' + '\n'.join(
                [f'{s.id}: {s.name}' for s in in_progress]))
        sys.exit(1)
    logging.info('No incomplete loading detected.')


def get_datasheet_path(submission, valid_extensions=['.xlsx', '.csv']):
    for extension in valid_extensions:
        datasheet_path = os.path.join(
            '/mnt', submission.submitting_user.name, submission.name,
            f'{submission.name}_datasheet{extension}')
        if os.path.exists(datasheet_path):
            return datasheet_path
        else:
            error_message = f'Could not find datasheet for {submission.name}: {datasheet_path}.'
            logging.error(error_message)
            raise FileNotFoundError(error_message)


def define_custom_args(submission, datasheet_path, num_proc):
    custom_args = [
        '--load', submission.name,
        '--data_sheet', datasheet_path, '--num_proc', str(num_proc),
        '--name', submission.name, '--is_cron_loading',
        '--study_user_string', submission.submitting_user.name,
        '--study_name', submission.name
    ]
    if submission.for_analysis:
        custom_args.append('--no_output')
    return custom_args


def load_submission(submission):
    datasheet_path = get_datasheet_path(submission)
    args = define_custom_args(
        submission=submission,
        datasheet_path=datasheet_path,
        num_proc=min(30, submission.number_samples))
    data_loader = DataLoader(args)
    try:
        data_loader.work_flow_manager.start_work_flow()
        submission.loading_started_date_time = data_loader.workflow_manager.date_time_str
        data_loader.update_submission(submission)
        logging.info(
            f'Data loading is complete for the {submission.name} submission object.')
    except Exception as e:
        submission.error_has_occured = True
        error_message = 'An error has occured while trying to load the Submission data.'
        logging.error(error_message)
        raise RuntimeError(error_message)
    finally:
        submission.save()


def get_submissions_to_load():
    submissions = \
        Submission.objects.filter(
            progress_status='transfer_to_framework_server_complete',
            error_has_occured=False,
            loading_started_date_time=None)
    if submissions:
        logging.info(
            f'The following submissions have been found to load: {", ".join(s.name for s in submissions)}.')
        # Return QuerySet
        return submissions
    else:
        logging.warning('No submission found for loading. Exiting.')
        sys.exit(1)


if __name__ == '__main__':

    lock_file = f'/var/lock/{os.path.basename(__file__)}.lock'

    # Only one cron job process can be running
    if lock_file_exists(lock_file):
        logging.info('Cron job process exists for the current script. Exiting.')
        sys.exit(1)

    # Main try block that always finishes with deleting of lock file
    try:
        # Generate the lock file to have only one cron running process
        generate_lock_file(lock_file)
        logging.info(f'Lock file generated. Current process ID: {os.getpid()}')
        check_incomplete_submissions()
        submissions = get_submissions_to_load()
        for s in submissions:
            load_submission(s)
    finally:
        remove_lock_file(lock_file)
