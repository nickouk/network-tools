#!/usr/bin/env python

'''
This module sends a command script to all devices held in a customer .info file
Please see grab-configs.py for more info on constructing the .info file
'''

import paramiko
import socket
import re
import datetime
import time
import sys
import getpass

from grab_configs import status_update
from grab_configs import raw_input_def
from grab_configs import shell_send
from grab_configs import print_flush
from grab_configs import clean_ansi
from grab_configs import get_defaults

'''
Functions
'''

def update_output_log(ip_addr,command_output):

    '''
    This function updates the command.log
    '''

    filename = "".join([cust_dir,"/command.log"])
    fileh = open(filename,"a")
    fileh.write("\n" + ip_addr + "\n")
    fileh.write(command_output)
    fileh.close()
    return

'''
Main module loop
'''

if __name__ == "__main__":

    ssh = paramiko.SSHClient()
    # If key is not in known hosts we ignore the warning
    # NOTE This may not be suitable for all and environments
    ssh.set_missing_host_key_policy(
            paramiko.AutoAddPolicy())

    # read defaults

    (def_cust,def_user) = get_defaults()


    print "\n============================"
    print "Send commands to all devices"
    print "============================\n"

    while True:
        cust = raw_input_def("Input the customer info file [%s]: " % def_cust,def_cust)
        username = raw_input_def("Input SSH username [%s]: " % def_user,def_user)
        password = getpass.getpass("Input SSH password: ")
        user_command = raw_input("Input command to execute on all devices: ")

        print "\n"
        print cust
        print username
        print "**PASSWORD HIDDEN**"
        print user_command

        yesno = raw_input("\nAre these details correct [y/n]: ").lower()
        print
        if yesno == "y":
            break


    '''
    Read the customer file to determine the folder and a list of IPs
    '''

    fileh = open(cust)
    cust_dir = fileh.readline().strip()
    ip_list = fileh.readlines()
    fileh.close()

    '''
    Main loop to connect to each IP, grab the config, store the config
    '''

    for ip_addr in ip_list:
        ip_addr = ip_addr.strip()

        '''
        Skip if ip_addr has been # out
        '''

        if '#' in ip_addr:
            print "Skipping %s" % (ip_addr.split("#")[1])
            status_update(cust_dir,ip_addr.split("#")[1],"","Skipped.")
            continue

        '''
        If the IP address contains a : then options have been added
        currently only :hp is supported
        :hp means we use an interactive shell to obtain the config
        '''

        hp = ""
        if ":" in ip_addr:
            ip_addr_list = ip_addr.split(":")
            ip_addr = ip_addr_list[0]
            if ip_addr_list[1] == "hp":
                hp = True


        '''
        Open the SSH Connection with some error handling
        '''

        print_flush("Establishing connection to %-15s > " % (ip_addr))

        try:
            ssh.connect(ip_addr,username=username,password=password,timeout=8)
        except paramiko.ssh_exception.AuthenticationException:
            print "Authentication failed."
            status_update(cust_dir,ip_addr,"","Authentication failed.")
            continue
        except socket.error:
            print "Could not connect."
            status_update(cust_dir,ip_addr,"","Connection error.")
            continue

        print_flush("[ Connection established ]")


        '''
        Send command and output to screen
        '''

        print_flush("[ sending command ]")

        '''
        HP does not support exec_command so we will use an interactive session for HP devices
        for cisco we will use the 'cleaner' exec_command method
        '''

        if not hp:
            # Cisco Device
            stdin, stdout, stderr = ssh.exec_command(user_command)
            command_output = stdout.read()
        else:
            # HP Device
            shell = ssh.invoke_shell(width=200, height=99999)
            # Strip MOTD
            output = shell.recv(2000)

            # Press enter,turn off paging,grab config
            shell_send("",1,1000,shell)
            shell_send("no page",1,500,shell)
            command_output = shell_send(user_command,15,2000,shell)
            ssh.close()

        command_output = clean_ansi(command_output)

        '''
        Store the output
        '''

        update_output_log(ip_addr,command_output)
        print " [ Output captured ]"

        '''
        End of main program Loop, repeat for each IP address in the customer info file
        '''

    '''
    All done!
    '''

    print "\nSend complete.\n"
