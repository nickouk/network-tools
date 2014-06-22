#!/usr/bin/env python

'''
This module references a customer info file which holds a customer directory name and a list of management IPs.
Prompt the user for SSH credentials then use those credntials to connect to each device in turn.
Once connected retrieve the config, lookup the hostname then store the config in the customer folder.

Check timestamps and file contents to ensure the job has run correctly.
Files are saved in the <customer dir> specified in the info file.
An activity.log is also updated in the <customer dir>

sample cust.info file:

acme-ltd            # customer directory should already exist, this must be the first line in the file
172.16.255.1
172.16.255.2
172.16.255.3:hp     # HP is for procurve kit, do not add :hp for Cisco/Juniper devices
#172.16.255.10      #  This line is skipped becuase it is # out.


'''

import paramiko
import socket
import re
import datetime
import time
import sys


'''
Functions
'''

def get_defaults():

    '''this function reads in defaults for the user inputs for the customer dir and user name
    tools.pref should exist in the same directory as the tools

    same tools.pref:

    acme-ltd.info
    username

    '''

    try:
        fileh = open("tools.pref")
    except IOError:
        return ['','']
    prefs = fileh.read().split()
    fileh.close()

    try:
        if prefs[1]:
            pass
    except IndexError:
        prefs.append('')

    return prefs



def clean_ansi(output):

    # Clean up the dirty HP formatting
    output = re.sub(r'\x1b\[[0-9]+?;[0-9]+?[A-z]','', output)
    output = re.sub(r'\x1b\[[0-9]+?[A-z]','', output)
    output = re.sub(r'\x1b\[\?[0-9]+?[A-z]','', output)
    output = re.sub(r'\x1b[A-z]','\n', output)
    output = output.replace('\r\n','\n')

    return output

def get_hostname(config):

    '''
    This function searches for the hostname field inside the config which is used as the filename
    '''

    hostname_se = re.search(r"hostname (.*)",config)
    if not hostname_se:
        return
    else:
        # HP store the hostname as "hostname" so we strip the "
        return hostname_se.group(1).strip().strip('"')


def status_update(ip_addr,hostname,status):

    '''
    This function updates the activity.log
    '''

    filename = "".join([cust_dir,"/activity.log"])
    fileh = open(filename,"a")
    status_msg = " ".join([str(datetime.datetime.now()).ljust(26),ip_addr.ljust(15),""])
    if hostname:
        # Only if we have a hostname, if not then something went wrong and we are logging an error
        status_msg += " ".join([hostname,""])
    status_msg += "".join([status,"\n"])
    fileh.write(status_msg)
    fileh.close()
    return

def raw_input_def(prompt,default):

    '''
    Adds a default for inputs
    '''

    usr_input = raw_input(prompt)
    if not usr_input:
        # If the user hit enter without inputting details we return the default
        return default
    else:
        return usr_input

def shell_send(cmd,wait,buf,shell):
    '''
    Sends a command to the SSH shell and waits. Adds a newline (simulates pressing enter)
    '''

    shell.send(cmd + "\n")
    time.sleep(wait)
    return shell.recv(buf)

def print_flush(output):
    '''
    prints without a newline and flushes the buffer so it appears on screen without delay
    '''
    sys.stdout.write(output)
    sys.stdout.flush()
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

    print
    print "============================="
    print "Grab configs from all devices"
    print "=============================\n"

    '''
    Prompt the user for customer info file and SSH credentials
    '''

    while True:
        cust = raw_input_def("Input the customer info file [%s]: " % def_cust,def_cust)
        username = raw_input_def("Input SSH username [%s]: " % def_user,def_user)
        password = raw_input("Input SSH password: ")

        print "\n"
        print cust
        print username
        print password

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
            status_update(ip_addr.split("#")[1],"","Skipped.")
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
            status_update(ip_addr,"","Authentication failed.")
            continue
        except socket.error:
            print "Could not connect."
            status_update(ip_addr,"","Connection error.")
            continue

        print_flush("[ Connection established ]")


        '''
        Get the config and print to screen
        '''

        print_flush("[ Retrieving the config ]")

        '''
        HP does not support exec_command so we will use an interactive session for HP devices
        for cisco we will use the 'cleaner' exec_command method
        '''

        if not hp:
            # Cisco Device
            stdin, stdout, stderr = ssh.exec_command("sh run")
            config = stdout.read()
        else:
            # HP Device
            shell = ssh.invoke_shell(width=200, height=99999)
            # Strip MOTD
            output = shell.recv(2000)

            # Press enter,turn off paging,grab config
            shell_send("",1,1000,shell)
            shell_send("no page",1,500,shell)
            config = shell_send("show run",6,65535,shell)
            shell.close()

            config = clean_ansi(config)

        # Use regex to find the hostname in the config
        hostname = get_hostname(config) + ".txt"

        if hostname == ".txt":
            print "Could not determine the hostname."
            status_update(ip_addr,"","Could not discover the hostname.")
            continue


        '''
        Store the config
        '''

        filename = "".join([cust_dir,"/",hostname])

        print "[ Storing the config as %s ]" % (filename)

        fileh = open(filename,"wb")
        fileh.write(config)
        fileh.close()

        status_update(ip_addr,hostname,"Completed.")

        '''
        End of main program Loop, repeat for each IP address in the customer info file
        '''

    '''
    All done!
    '''

    print "\nConfig grab complete.  Please check the file timestamps and file contents then upload to Atlas.\n"
