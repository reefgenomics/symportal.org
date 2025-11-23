#!/usr/bin/env python3
"""
SymPortal Output Retry Script

Command-line tool for checking status and retrying output generation for SymPortal submissions.

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


def parse_dataset_uids(list_of_data_set_uids):
    """
    Parse a comma-separated string of dataset UIDs into a list of integers.
    
    Args:
        list_of_data_set_uids: Comma-separated string of dataset UIDs
        
    Returns:
        List of integer dataset UIDs, with empty strings filtered out
    """
    return [int(uid.strip()) for uid in list_of_data_set_uids.split(',') if uid.strip()]


def check_submission_status(submission_name, status_limit=5):
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

        # More precise matching: look for exact dataset ID matches
        matching_analyses = []
        for analysis in DataAnalysis.objects.all().order_by('-id'):
            dataset_uids = parse_dataset_uids(analysis.list_of_data_set_uids)
            if dataset_id in dataset_uids:
                matching_analyses.append(analysis)

        print(f"\n=== DataAnalysis Records ===")
        print(f"Found {len(matching_analyses)} matching DataAnalysis records")
        if status_limit == 0:
            print("Showing: all matching analyses")
        else:
            print(f"Showing: up to {status_limit} most recent analyses")

        if matching_analyses:
            from dbApp.models import AnalysisType, CladeCollectionType
            iterable = matching_analyses if status_limit == 0 else matching_analyses[:status_limit]
            for i, analysis in enumerate(iterable):
                print(f"  {i+1}. ID: {analysis.id}, Name: {analysis.name}")
                print(f"     Dataset UIDs: {analysis.list_of_data_set_uids}")
                # Check global analysis types
                at_count = AnalysisType.objects.filter(data_analysis_from=analysis).count()
                # Check how many CladeCollectionType belong to this dataset within this analysis
                cct_count = CladeCollectionType.objects.filter(
                    analysis_type_of__data_analysis_from=analysis,
                    clade_collection_found_in__data_set_sample_from__data_submission_from_id=dataset_id
                ).count()
                print(f"     Analysis Types: {at_count}")
                print(f"     Dataset-linked CladeCollectionTypes: {cct_count}")
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


def retry_output_generation(submission_name, num_proc=20, analysis_id=None, no_ordinations=False):
    """Retry output generation for a submission."""
    try:
        sub = Submission.objects.get(name=submission_name)
        dataset_id = sub.associated_dataset.id

        print(f"=== Retrying Output Generation: {submission_name} ===")
        print(f"Submission ID: {sub.id}")
        print(f"Dataset ID: {dataset_id}")
        print(f"Study ID: {sub.associated_study.id}")

        from dbApp.models import AnalysisType, CladeCollectionType

        # If analysis_id provided, validate and use it directly
        selected_analysis = None
        if analysis_id is not None:
            try:
                a = DataAnalysis.objects.get(id=int(analysis_id))
                dataset_uids = parse_dataset_uids(a.list_of_data_set_uids)
                if dataset_id not in dataset_uids:
                    print(f"Error: Provided analysis {analysis_id} does not include dataset {dataset_id}.")
                    return False
                selected_analysis = a
            except DataAnalysis.DoesNotExist:
                print(f"Error: DataAnalysis with id {analysis_id} not found.")
                return False
        else:
            # Find analyses containing the dataset id
            matching_analyses = []
            for analysis in DataAnalysis.objects.all().order_by('-id'):
                dataset_uids = parse_dataset_uids(analysis.list_of_data_set_uids)
                if dataset_id in dataset_uids:
                    matching_analyses.append(analysis)

            if not matching_analyses:
                print("Error: No matching DataAnalysis found for this dataset!")
                print("Output generation requires a completed analysis phase.")
                return False

            # Prefer the most recent analysis that has dataset-linked CladeCollectionTypes (>0)
            # Falling back to one that has analysis types (>0), as a weaker signal
            best_with_ccts = None
            best_with_ats = None
            for analysis in matching_analyses:
                cct_count = CladeCollectionType.objects.filter(
                    analysis_type_of__data_analysis_from=analysis,
                    clade_collection_found_in__data_set_sample_from__data_submission_from_id=dataset_id
                ).count()
                at_count = AnalysisType.objects.filter(data_analysis_from=analysis).count()
                print(f"Checking DataAnalysis {analysis.id}: {at_count} analysis types, {cct_count} dataset-linked CCTs")
                if cct_count > 0 and best_with_ccts is None:
                    best_with_ccts = analysis
                if at_count > 0 and best_with_ats is None:
                    best_with_ats = analysis

            selected_analysis = best_with_ccts or best_with_ats

        if not selected_analysis:
            print("Error: No suitable DataAnalysis with dataset-linked results found!")
            # Provide diagnostics
            total_ccs = 0
            try:
                from dbApp.models import CladeCollection
                total_ccs = CladeCollection.objects.filter(
                    data_set_sample_from__data_submission_from_id=dataset_id
                ).count()
            except Exception:
                pass
            print(f"Diagnostics: Dataset {dataset_id} has {total_ccs} CladeCollections in DB.")
            print("Try re-running analysis including this dataset or verify the dataset was fully loaded.")
            return False

        if not selected_analysis:
            print("Error: No DataAnalysis with analysis types found!")
            print("Available analyses:")
            for analysis in DataAnalysis.objects.all().order_by('-id')[:5]:
                at_count = AnalysisType.objects.filter(data_analysis_from=analysis).count()
                print(f"  - ID {analysis.id}: {at_count} analysis types")
            return False
        print(f"Using DataAnalysis ID: {selected_analysis.id}")
        print(f"DataAnalysis name: {selected_analysis.name}")

        # Create the workflow arguments
        args = [
            '--output_study_from_analysis',
            str(sub.associated_study.id),
            '--num_proc', str(num_proc),
            '--data_analysis_id', str(selected_analysis.id),
        ]

        if no_ordinations:
            args.append('--no_ordinations')

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
    parser.add_argument('--analysis_id', type=int, default=None,
                        help='Optional: explicitly set DataAnalysis ID to use for output')
    parser.add_argument('--no_ordinations', action='store_true',
                        help='Skip ordinations during output generation')
    parser.add_argument('--num_proc', type=int, default=20,
                        help='Number of processes to use for output generation (default: 20)')
    parser.add_argument('--status_limit', type=int, default=5,
                        help='How many analyses to show with --status (0 = all, default: 5)')

    args = parser.parse_args()

    if args.status:
        success = check_submission_status(args.status, args.status_limit)
        sys.exit(0 if success else 1)

    elif args.get_output:
        success = retry_output_generation(
            args.get_output,
            args.num_proc,
            args.analysis_id,
            args.no_ordinations,
        )
        sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()