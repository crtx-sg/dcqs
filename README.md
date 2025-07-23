# dcqs
Dicom Criticality Queuing System
------

Install all libraries in requirements.txt

docker-compose up

Upload Dicom files using pacs-upload.py <zip file> or <directory>

Check the files in Orthanc Pacs

Query the Orthanc Pacs server using pacs-query.py


Errors:
When starting docker if error is received, kill all containers
docker rm $(docker ps -a -q)

