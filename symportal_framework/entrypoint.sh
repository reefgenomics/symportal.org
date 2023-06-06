#!/bin/bash

# Wait for the database to be ready (optional)
# Add any other necessary wait conditions

# Run the database migration command
python manage.py migrate && \
python populate_db_ref_seqs.py

# Start an interactive shell
exec /bin/bash
