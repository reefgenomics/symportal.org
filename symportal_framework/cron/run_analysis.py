import os
import sys
import django
import logging
from datetime import datetime

from load_data import generate_lock_file, lock_file_exists, remove_lock_file

# Initialize Django
django.setup()
# Import from installed Apps
import main
from dbApp.models import Submission, DataAnalysis

# Configure logging
logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class AnalysisRunner:
    def __init__(self, args):
        logging.info('Initializing SymPortal Workflow Manager...')
        self.workflow_manager = main.SymPortalWorkFlowManager(args)
        logging.info(
            'Initializing of Symportal Workflow Manager has been completed.')

    def update_analyzed_submission(self, submission):
        submission.progress_status = 'framework_analysis_complete'
        submission.analysis_complete_date_time = \
            datetime.utcnow().strftime('%Y%m%dT%H%M%S')
        submission.save()
        logging.info(
            f'The status of submission {submission.name} has been changed to {submission.progress_status}.')

    def update_output_submission(self, submission):
        sub_obj.progress_status = 'framework_output_complete'
        submission.study_output_complete_date_time = \
            datetime.utcnow().strftime('%Y%m%dT%H%M%S')
        submission.framework_results_dir_path = self.workflow_manager.output_dir
        submission.save()
        logging.info(
            f'The status of submission {submission.name} has been changed to {submission.progress_status}.')


def get_submissions(status, process_type):
    submissions = \
        Submission.objects.filter(
            progress_status=status,
            error_has_occured=False,
            for_analysis=True).all()
    if submissions:
        logging.info(
            f'The following submissions have been found to {process_type}: {", ".join(s.name for s in submissions)}.')
        # Return QuerySet
        return submissions
    else:
        logging.warning(f'No submission found to {process_type}. Exiting.')
        sys.exit(1)


def analyze(submissions, dataset_string, num_proc, analysis_name):
    analysis_runner = AnalysisRunner([
        '--analyse_next', dataset_string, '--num_proc', num_proc,
        '--no_output',
        '--name', analysis_name
    ])
    for submission in submissions:
        try:
            submission.analysis_started_date_time = \
                analysis_runner.workflow_manager.date_time_str
            logging.info(
                f'Starting the workflow  for Submission: {submission.name}.')
            analysis_runner.workflow_manager.start_work_flow()
            analysis_runner.update_analyzed_submission(submission)
        except Exception as e:
            error_message = f'An error has occurred while trying to analyze the ' \
                            f'Submission: {submission.name}.'
            logging.error(error_message)
            raise RuntimeError(error_message)


def output(submissions, num_proc):
    for submission in submissions:
        try:
            latest_data_analysis = DataAnalysis.objects.filter(
                list_of_data_set_uids__contains=str(
                    submission.associated_dataset.id)).order_by('-id')[0]
            analysis_runner = AnalysisRunner([
                '--output_study_from_analysis',
                str(submission.associated_study.id),
                '--num_proc', num_proc,
                '--data_analysis_id', str(latest_data_analysis.id),
            ])
            submission.study_output_started_date_time = \
                analysis_runner.workflow_manager.date_time_str
            submission.save()
            analysis_runner.workflow_manager.start_work_flow()
            analysis_runner.update_output_submission(submission)
        except Exception as e:
            error_message = f'An error has occurred while trying to output the ' \
                            f'Submission: {submission.name}.'
            logging.error(error_message)
            raise RuntimeError(error_message)


if __name__ == '__main__':

    lock_file = f'/var/lock/{os.path.basename(__file__)}.lock'
    num_proc = '30'

    # Only one cron job process can be running
    if lock_file_exists(lock_file):
        sys.exit(1)

    # Main try block that always finishes with deleting of lock file
    try:
        # Generate the lock file to have only one cron running process
        generate_lock_file(lock_file)

        submissions = get_submissions(status='framework_loading_complete',
                                      process_type='analyze')
        dataset_objects = [s.associated_dataset for s in submissions]
        dataset_string = ','.join([str(d.id) for d in dataset_objects])
        analysis_name = f'{datetime.utcnow().strftime("%Y%m%dT%H%M%S")}_DBV'
        analyze(submissions, dataset_string, num_proc, analysis_name)

        submissions = get_submissions(status='framework_analysis_complete',
                                      process_type='output')
        output(submissions, num_proc)
    finally:
        remove_lock_file(lock_file)
        logging.info('Analysis for loaded submissions has been completed.')
