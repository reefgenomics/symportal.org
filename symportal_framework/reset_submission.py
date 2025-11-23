#!/usr/bin/env python3
import django
django.setup()
from dbApp.models import Submission
from datetime import datetime

def reset_submission_to_start(submission_name):
    """Reset a submission to restart from the beginning of framework processing."""
    try:
        sub = Submission.objects.get(name=submission_name)

        print(f"Resetting submission: {submission_name}")
        print(f"Current status: {sub.progress_status}")

        # Reset status to just after SFTP transfer
        sub.progress_status = 'transfer_to_framework_server_complete'

        # Clear all completion timestamps
        sub.loading_started_date_time = None
        sub.loading_complete_date_time = None
        sub.analysis_started_date_time = None
        sub.analysis_complete_date_time = None
        sub.study_output_started_date_time = None
        sub.study_output_complete_date_time = None

        # Clear results path
        sub.framework_results_dir_path = None

        # Clear error flags
        sub.error_has_occured = False

        sub.save()

        print(f"Submission reset to status: {sub.progress_status}")
        print("The submission will be picked up by the next cron cycle.")

        return True

    except Submission.DoesNotExist:
        print(f"Error: Submission '{submission_name}' not found!")
        return False
    except Exception as e:
        print(f"Error resetting submission: {e}")
        return False

if __name__ == '__main__':
    import sys
    if len(sys.argv) != 2:
        print("Usage: python reset_submission.py <submission_name>")
        sys.exit(1)

    submission_name = sys.argv[1]
    success = reset_submission_to_start(submission_name)
    sys.exit(0 if success else 1)