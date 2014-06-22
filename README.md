network-tools
=============

Python scripts to automate networking tasks.


Requirements:
-------------

Paramiko - https://github.com/paramiko/paramiko


Overview
--------

All tools require a 'cust.info' file located in the same directory as the network tools.  The 'cust.info' file should be in the following format:

acme-ltd            # customer directory should already exist, this must be the first line in the file
172.16.255.1
172.16.255.2
172.16.255.3:hp     # HP is for procurve kit, do not add :hp for Cisco/Juniper devices
#172.16.255.10      #  This line is skipped becuase it is # out.

From the example above you must have created a directory named 'acme-ltd'.  Do not use # to add comments # is only allowed at the beginning of a line to indicate that the device should be skipped.

You can have multiple customer.info files and directories for working on different sets of devices.  They can be for different customers, or departments etc.

grab_configs.py - will log onto each device and download the latest config
send_commands.py - will send a command to each device and store the output as 'command.log' in the custoemr dir.

grab_configs.py contains function defintions for all modules in this repositiory.

