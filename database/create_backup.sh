#!/bin/bash

# Get the current date and time in the format: YYYYMMDD_HHMMSS
current_datetime=$(date +"%Y%m%d_%H%M%S")

# Create the filename for the backup using the current date and time
backup_filename="/tmp/backups/postgresql_${current_datetime}.sql"

# Replace "your_username" and "your_database_name" with actual values
pg_dump -U humebc -d symportal_database -h 134.34.126.43 -f "$backup_filename"

# Check the exit status of pg_dump to determine if the backup was successful
if [ $? -eq 0 ]; then
  echo "Backup created successfully: $backup_filename"
else
  echo "Backup creation failed!"
fi
