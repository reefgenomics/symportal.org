#!/usr/bin/env python3
"""
Switch out the nginx config files so that the symportal is down for maintenance page is displayed
Stop the sp_stack process
This then allows us to do the db work.
We run this seperately from the sync_db.py script as this and the stop_symportal.py scripts
have to be run as root. Wheras the sync_db.py must be run as humebc for peer authentication
of the database purposes.
"""
import os
import subprocess

if os.path.exists('/home/humebc/symportal.org/nginx/conf.d/virtual.running.conf') and os.path.exists('/home/humebc/symportal.org/nginx/conf.d/virtual.maintenance.conf.bak'):
    # Then we are currently in the live state and we want to change to the
    # maintenance conf file
    os.rename('/home/humebc/symportal.org/nginx/conf.d/virtual.running.conf', '/home/humebc/symportal.org/nginx/conf.d/virtual.running.conf.bak')
    os.rename('/home/humebc/symportal.org/nginx/conf.d/virtual.maintenance.conf.bak', '/home/humebc/symportal.org/nginx/conf.d/virtual.maintenance.conf')
elif os.path.exists('/home/humebc/symportal.org/nginx/conf.d/virtual.running.conf.bak') and os.path.exists('/home/humebc/symportal.org/nginx/conf.d/virtual.maintenance.conf'):
    # Then we are already in maintenance state
    pass
else:
    raise RuntimeError('Check .conf files. Something seems to have gone wrong.')

# Restart the ngnix server to ensure that the conf files are being correctly read
subprocess.run(['nginx', '-s', 'reload'], check=True)

# At this point people can no longer access symportal.org
# now stop the sp_stack so that the symportal_database can be dropped
subprocess.run(['supervisorctl', 'stop', 'sp_stack'], check=True)