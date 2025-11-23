#!/usr/bin/env python3
"""
SymPortal Output Retry Script
        print("\n=== DataAnalysis Records ===")
        print(f"Found {len(matching_analyses)} matching DataAnalysis records") command-line tool for checking status and retrying output generation for SymPortal submissions.

Usage:
    ./retry_output.py --status <submission_name>     # Check submission status
    ./retry_output.py --get_output <submission_name> # Retry output generation
    ./retry_output.py --help                         # Show help

Examples:
    ./retry_output.py --status "20250709T082500_colinlu1"
    ./retry_output.py --get_output "20250709T082500_colinlu1"
"""

import sys
import django
import argparse
from datetime import datetime

# Initialize Django
django.setup()
# Import from installed Apps
import main as workflow_main
from dbApp.models import Submission, DataAnalysis


def check_submission_status(submission_name):
    """Check and display the status of a submission."""
    try:
        sub = Submission.objects.get(name=submission_name)

        print(f"=== Submission Status: {submission_name} ===")
        print(f"ID: {sub.id}")
        print(f"Progress Status: {sub.progress_status}")
        print(f"Associated Dataset ID: {sub.associated_dataset.id}")
        print(f"Associated Study ID: {sub.associated_study.id}")
        print(f"Created: {sub.submission_date_time}")

        if sub.loading_complete_date_time:
            print(f"Data Loading Complete: {sub.loading_complete_date_time}")
        if sub.analysis_complete_date_time:
            print(f"Analysis Complete: {sub.analysis_complete_date_time}")
        if sub.study_output_started_date_time:
            print(f"Output Started: {sub.study_output_started_date_time}")
        if sub.study_output_complete_date_time:
            print(f"Output Complete: {sub.study_output_complete_date_time}")
        if sub.framework_results_dir_path:
            print(f"Results Directory: {sub.framework_results_dir_path}")

        # Check for matching DataAnalysis records
        dataset_id = sub.associated_dataset.id
        matching_analyses = DataAnalysis.objects.filter(
            list_of_data_set_uids__contains=str(dataset_id)
        ).order_by('-id')

        print(f"\n=== DataAnalysis Records ===")
        print(f"Found {len(matching_analyses)} matching DataAnalysis records")

        if matching_analyses:
            for i, analysis in enumerate(matching_analyses[:5]):  # Show top 5
                print(f"  {i+1}. ID: {analysis.id}, Name: {analysis.name}")
                if i == 0:
                    print(f"     Latest - Dataset UIDs: {analysis.list_of_data_set_uids}")
        else:
            print("  No matching DataAnalysis found - output generation may fail!")

        return True

    except Submission.DoesNotExist:
        print(f"Error: Submission '{submission_name}' not found!")
        return False
    except Exception as e:
        print(f"Error checking submission status: {e}")
        import traceback
        traceback.print_exc()
        return False


def retry_output_generation(submission_name, num_proc=20):
    """Retry output generation for a submission."""
    try:
        sub = Submission.objects.get(name=submission_name)
        dataset_id = sub.associated_dataset.id

        print(f"=== Retrying Output Generation: {submission_name} ===")
        print(f"Submission ID: {sub.id}")
        print(f"Dataset ID: {dataset_id}")
        print(f"Study ID: {sub.associated_study.id}")

        # Check for DataAnalysis records
        matching_analyses = DataAnalysis.objects.filter(
            list_of_data_set_uids__contains=str(dataset_id)
        ).order_by('-id')

        if not matching_analyses:
            print("Error: No matching DataAnalysis found for this dataset!")
            print("Output generation requires a completed analysis phase.")
            return False

        latest_data_analysis = matching_analyses[0]
        print(f"Using DataAnalysis ID: {latest_data_analysis.id}")
        print(f"DataAnalysis name: {latest_data_analysis.name}")

        # Create the workflow arguments
        args = [
            '--output_study_from_analysis',
            str(sub.associated_study.id),
            '--num_proc', str(num_proc),
            '--data_analysis_id', str(latest_data_analysis.id),
        ]

        print(f"Workflow arguments: {args}")

        # Initialize the workflow manager
        print("Initializing workflow manager...")
        workflow_manager = workflow_main.SymPortalWorkFlowManager(args)

        # Update the submission start time
        sub.study_output_started_date_time = workflow_manager.date_time_str
        sub.progress_status = 'framework_output_in_progress'
        sub.save()

        print("Starting workflow execution...")
        workflow_manager.start_work_flow()

        # Update submission to complete
        sub.progress_status = 'framework_output_complete'
        sub.study_output_complete_date_time = datetime.utcnow().strftime('%Y%m%dT%H%M%S')
        sub.framework_results_dir_path = workflow_manager.output_dir
        sub.save()

        print("Output phase completed successfully!")
        print(f"Results directory: {workflow_manager.output_dir}")
        return True

    except Submission.DoesNotExist:
        print(f"Error: Submission '{submission_name}' not found!")
        return False
    except Exception as e:
        print(f"Error during output generation: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main function to handle command-line arguments."""
    parser = argparse.ArgumentParser(
        description='SymPortal Output Retry Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --status "20250709T082500_colinlu1"
  %(prog)s --get_output "20250709T082500_colinlu1"
  %(prog)s --get_output "20250709T082500_colinlu1" --num_proc 10
        """
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--status', metavar='SUBMISSION_NAME',
                       help='Check the status of a submission')
    group.add_argument('--get_output', metavar='SUBMISSION_NAME',
                       help='Retry output generation for a submission')

    parser.add_argument('--num_proc', type=int, default=20,
                        help='Number of processes to use for output generation (default: 20)')

    args = parser.parse_args()

    if args.status:
        success = check_submission_status(args.status)
        sys.exit(0 if success else 1)

    elif args.get_output:
        success = retry_output_generation(args.get_output, args.num_proc)
        sys.exit(0 if success else 1)


if __name__ == '__main__':
	main()