#!/usr/bin/env python3
"""
Switch out the nginx config files so that symportal is up
Start the sp_stack process
This then allows us to do the db work.
We run this seperately from the sync_db.py script as this and the stop_symportal.py scripts
have to be run as root. Wheras the sync_db.py must be run as humebc for peer authentication
of the database purposes.
"""
import os
import subprocess

# At this point people can no longer access symportal.org
# now stop the sp_stack so that the symportal_database can be dropped
subprocess.run(['supervisorctl', 'start', 'sp_stack'], check=True)

if os.path.exists('/home/humebc/symportal.org/nginx/conf.d/virtual.running.conf.bak') and os.path.exists('/home/humebc/symportal.org/nginx/conf.d/virtual.maintenance.conf'):
    # Then we are currently in the maintenance state and we want to change to the
    # running conf file
    os.rename('/home/humebc/symportal.org/nginx/conf.d/virtual.running.conf.bak', '/home/humebc/symportal.org/nginx/conf.d/virtual.running.conf')
    os.rename('/home/humebc/symportal.org/nginx/conf.d/virtual.maintenance.conf', '/home/humebc/symportal.org/nginx/conf.d/virtual.maintenance.conf.bak')
elif os.path.exists('/home/humebc/symportal.org/nginx/conf.d/virtual.running.conf') and os.path.exists('/home/humebc/symportal.org/nginx/conf.d/virtual.maintenance.conf.bak'):
    # Then we are already in running state
    pass
else:
    raise RuntimeError('Check .conf files. Something seems to have gone wrong.')

# Restart the ngnix server to ensure that the conf files are being correctly read
subprocess.run(['nginx', '-s', 'reload'], check=True)