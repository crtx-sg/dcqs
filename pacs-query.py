## Query Pacs for Dicom and retrive

import os
import sys
import time
from datetime import datetime, timedelta
import httpx
from pyorthanc import Orthanc, Study

# --- Configuration ---
# URL of your Orthanc Server's REST API
ORTHANC_URL = 'http://localhost:8042'
ORTHANC_USERNAME = 'orthanc'
ORTHANC_PASSWORD = 'orthanc'

# How far back to search for new studies on each run.
QUERY_WINDOW = timedelta(minutes=60)

# Directory to save the retrieved DICOM files
DOWNLOAD_DIR = 'retrieved_studies'

# A simple file-based database to track which studies have been processed.
PROCESSED_UIDS_FILE = 'processed_study_uids.txt'

def load_processed_uids():
    """Loads the set of already processed Study Instance UIDs from a file."""
    if not os.path.exists(PROCESSED_UIDS_FILE):
        return set()
    with open(PROCESSED_UIDS_FILE, 'r') as f:
        return {line.strip() for line in f if line.strip()}

def save_processed_uid(uid):
    """Appends a new processed Study Instance UID to our tracking file."""
    with open(PROCESSED_UIDS_FILE, 'a') as f:
        f.write(uid + '\n')

def query_for_new_studies(client, processed_uids):
    """
    Queries the Orthanc server directly for recent studies.

    This function queries for studies within the time window defined by
    QUERY_WINDOW and filters out any that have already been processed.
    """
    print("Querying Orthanc for new studies...")

    now = datetime.now()
    start_time = now - QUERY_WINDOW
    
    # Format date for the query (YYYYMMDD)
    query_date = start_time.strftime('%Y%m%d')

    # Construct the find query payload.
    # We ask for all studies from the start date onwards.
    # We will filter by the precise time window in the code below.
    query = {
        'Level': 'Study',
        'Query': {
            'StudyDate': f'{query_date}-',  # Search from this date forward
        }
    }

    new_studies = []
    try:
        # Use post_tools_find to query the Orthanc database directly
        study_ids = client.post_tools_find(query)
        
        print(f"Found {len(study_ids)} candidate studies since {query_date}.")

        for study_id in study_ids:
            # Get the full study information
            study = Study(study_id, client)
            main_info = study.get_main_information().get('MainDicomTags', {})
            
            study_uid = main_info.get('StudyInstanceUID')
            if not study_uid:
                print(f"Warning: Found a study (ID: {study_id}) with no StudyInstanceUID. Skipping.")
                continue

            # Skip if we have already processed this study
            if study_uid in processed_uids:
                continue

            # Now, check if the study is within our precise time window
            study_date_str = main_info.get('StudyDate')
            study_time_str = main_info.get('StudyTime', '000000')

            if not study_date_str:
                continue

            try:
                # DICOM time can have fractional seconds, so we handle that by splitting.
                study_datetime_str = f"{study_date_str}{study_time_str.split('.')[0]}"
                study_datetime = datetime.strptime(study_datetime_str, '%Y%m%d%H%M%S')

                if study_datetime >= start_time:
                    print(f"  -> Found new study: {study_uid} from {study_datetime}")
                    new_studies.append({'ID': study_id})
                
            except ValueError:
                print(f"Warning: Could not parse date/time for study {study_uid} ('{study_date_str}' '{study_time_str}'). Skipping.")
                continue

    except Exception as e:
        print(f"Error during study query: {e}", file=sys.stderr)

    return new_studies

def retrieve_and_save_study(client, study_orthanc_id):
    """
    Retrieves a study's DICOM instances and saves them locally.
    """
    try:
        study = Study(study_orthanc_id, client)
        study_uid = study.get_main_information().get('MainDicomTags', {}).get('StudyInstanceUID')
        
        print(f"Retrieving study {study_uid} (Orthanc ID: {study_orthanc_id})")

        study_path = os.path.join(DOWNLOAD_DIR, study_uid)
        os.makedirs(study_path, exist_ok=True)

        instance_count = 0
        for series in study.series:
            for instance in series.instances:
                dicom_file_bytes = instance.get_file()
                instance_filename = f"{instance.uid}.dcm"
                instance_path = os.path.join(study_path, instance_filename)
                with open(instance_path, 'wb') as f:
                    f.write(dicom_file_bytes)
                instance_count += 1
        
        print(f"Successfully saved {instance_count} instances to {study_path}")
        return study_uid

    except Exception as e:
        print(f"Error retrieving or saving study ID {study_orthanc_id}: {e}", file=sys.stderr)
        return None

def main():
    """
    Main function to run the query and retrieval loop.
    """
    print("Starting DICOM Criticality Queuing System")
    
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    
    processed_uids = load_processed_uids()
    print(f"Loaded {len(processed_uids)} previously processed study UIDs.")

    try:
        client = Orthanc(ORTHANC_URL, username=ORTHANC_USERNAME, password=ORTHANC_PASSWORD)
        print(f"Successfully connected to Orthanc at {ORTHANC_URL}")

        new_studies_to_process = query_for_new_studies(client, processed_uids)
        
        if not new_studies_to_process:
            print("No new studies to process at this time.")
            return

        print(f"\nBeginning retrieval of {len(new_studies_to_process)} new studies...")

        for study_data in new_studies_to_process:
            orthanc_id = study_data['ID']
            
            retrieved_study_uid = retrieve_and_save_study(client, orthanc_id)

            if retrieved_study_uid:
                save_processed_uid(retrieved_study_uid)
                print(f"Successfully processed and marked study {retrieved_study_uid} as complete.")
                print("-" * 20)

    except httpx.ConnectError as e:
        print(f"FATAL: Could not connect to Orthanc at {ORTHANC_URL}. Please check the URL and ensure Orthanc is running.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error of type {type(e).__name__} occurred: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
