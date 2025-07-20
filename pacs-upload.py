# upload Dicom file to Orthanc Pacs server.

import os
import sys
import argparse
import httpx
from pyorthanc import Orthanc, upload

def main():
    """
    Main function to handle command-line arguments and upload DICOM files.
    """
    parser = argparse.ArgumentParser(
        description='Upload a DICOM directory or a zip file to an Orthanc server.'
    )
    parser.add_argument(
        'input_path',
        type=str,
        help='The full path to the DICOM directory or zip file.'
    )
    args = parser.parse_args()

    input_path = args.input_path

    # Check if the provided path exists
    if not os.path.exists(input_path):
        print(f"Error: The path '{input_path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    # Check if the path is a directory or a file
    is_directory = os.path.isdir(input_path)
    is_zip_file = input_path.lower().endswith('.zip')

    if not is_directory and not is_zip_file:
        print(f"Error: The path '{input_path}' is not a directory or a .zip file.", file=sys.stderr)
        sys.exit(1)

    try:
        client = Orthanc('http://localhost:8042', username='orthanc', password='orthanc')

        print("Current data on server...")
        patient_ids = client.get_patients()
        print(f"  Patient IDs: {patient_ids}")
        studies = client.get_studies()
        print(f"  Study IDs: {studies}")

        print(f"\nUploading from '{input_path}'...")
        
        if is_directory:
            print("  -> Detected a directory. Uploading recursively...")
            uploaded_files = upload(client, input_path, recursive=True, check_before_upload=True)
        else: # It's a zip file
            print("  -> Detected a zip file. Uploading...")
            uploaded_files = upload(client, input_path)
        
        if not uploaded_files:
            print("\nNo new files were uploaded.")
        else:
            print(f"\nSuccessfully uploaded {len(uploaded_files)} instances.")

    except httpx.ConnectError as e:
        print(f"Error connecting to Orthanc: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An error of type {type(e).__name__} occurred: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
