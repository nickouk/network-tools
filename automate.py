#!/usr/bin/env python

'''
This module references a customer info file which holds a customer directory
name and a list of management IPs. Prompt the user for SSH credentials then
use those credentials to connect to each device in turn. Once connected retrieve
the config, lookup the hostname then store the config in the customer folder.

Check timestamps and file contents to ensure the job has run correctly.
Files are saved in the <customer dir> specified in the info file.
An activity.log is also updated in the <customer dir>

sample cust.info file:

acme-ltd            # customer dir should already exist, must be the first line
172.16.255.1
172.16.255.2
172.16.255.3:model,hp     # HP is for procurve kit, do not add :hp for Cisco/Juniper
#172.16.255.10      #  This line is skipped becuase it is # out.
172.16.255.4:conn,telnet:user,test,temp123
172.16.255.5:user,test,temp123,enablepass


'''

import paramiko
import socket
import re
import datetime
import time
import sys
import getpass
import telnetlib


# Functions


def get_defaults():

    '''this function reads in defaults for the user inputs customer dir and user name
    tools.pref should exist in the same directory as the tools.

    tools.pref is not required.

    same tools.pref:

    acme-ltd.info
    username

    '''

    try:
        fileh_def = open("tools.pref")
    except IOError:
        return ['', '']
    prefs = fileh_def.read().split()
    fileh_def.close()

    try:
        if prefs[1]:
            pass
    except IndexError:
        prefs.append('')

    return prefs


def clean_ansi(clean):

    '''
    This functions cleans ANSI code from the output
    '''

    # Clean up the dirty HP formatting
    clean = re.sub(r'\x1b\[[0-9]+?;[0-9]+?[A-z]', '', clean)
    clean = re.sub(r'\x1b\[[0-9]+?[A-z]', '', clean)
    clean = re.sub(r'\x1b\[\?[0-9]+?[A-z]', '', clean)
    clean = re.sub(r'\x1b[A-z]', '\n', clean)
    clean = clean.replace('\r\n', '\n')

    return clean

def get_hostname(dev_output):

    '''
    This function searches for the hostname field inside the config which is
    used as the filename.
    '''

    hostname_se = re.search(r"hostname (.*)", dev_output)
    if not hostname_se:
        return
    else:
        # HP store the hostname as "hostname" so we strip the "
        return hostname_se.group(1).strip().strip('"')



def status_update(folder, host_ip, name, status):

    '''
    This function updates the activity.log
    '''

    su_filename = "".join([folder, "/activity.log"])
    su_fileh = open(su_filename, "a")
    su_status_msg = " ".join([str(datetime.datetime.now()).ljust(26), host_ip.ljust(15), ""])
    if name:
        # Only if we have a hostname, if not then something went wrong.
        su_status_msg += " ".join([name, ""])
    su_status_msg += "".join([status, "\n"])
    su_fileh.write(su_status_msg)
    su_fileh.close()
    return

def update_cmd_log(log_cust_dir, log_ip_addr, log_command_output):

    '''
    This function updates the command.log
    '''

    filename = "".join([log_cust_dir, "/command.log"])
    log_fileh = open(filename, "a")
    log_fileh.write("\n---------------------------------------------------------\n" + log_ip_addr + "\n")
    log_fileh.write(log_command_output)
    log_fileh.close()
    return


def raw_input_def(prompt, default):

    '''
    Adds a default for inputs
    '''

    usr_input = raw_input(prompt)
    if not usr_input:
        # If the user hit enter without inputting details we return the default
        return default
    else:
        return usr_input

def shell_send(cmd, wait, buf, ssh_shell, shell_is_telnet):
    '''
    Sends a command to the SSH or telnet shell and waits. Adds a newline
    (simulates pressing enter)
    '''

    if not shell_is_telnet:
        ssh_shell.send(cmd + "\n")
        time.sleep(wait)
        return ssh_shell.recv(buf)
    else:
        ssh_shell.write(cmd + "\r\n")
        time.sleep(wait)
        return ssh_shell.read_very_eager()

def print_flush(flush_output):
    '''
    prints without a newline and flushes the buffer so it appears on screen
    without delay
    '''
    sys.stdout.write(flush_output)
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

    (def_cust, def_user) = get_defaults()

    print
    print "============================="
    print "Grab configs from all devices"
    print "=============================\n"

    '''
    Prompt the user for customer info file and SSH credentials
    '''

    while True:
        cust = raw_input_def("Input the customer info file [%s]: " % def_cust, def_cust)
        input_username = raw_input_def("Input SSH username [%s]: " % def_user, def_user)
        input_password = getpass.getpass("Input SSH password: ")
        cmd = raw_input("Enter commands seperate by commas or press enter to grab configs : ")

        if not cmd: cmd = "show run"

        cmd_list = cmd.split(",")

        print "\n"
        print cust
        print input_username
        print "**PASSWORD HIDDEN**"

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
    Main loop to connect to each IP
    '''

    for ip_addr in ip_list:
        ip_addr = ip_addr.strip()

        '''
        Skip if ip_addr has been # out
        '''

        if '#' in ip_addr:
            print "Skipping %s" % (ip_addr.split("#")[1])
            status_update(cust_dir, ip_addr.split("#")[1], "", "*** Skipped. ***")
            continue

        '''
        If the IP address contains a : then options have been added
        :model,hp means we use an interactive shell
        :user,tempuser,pass123,enablepass - enablepass is optional
        :conn,telnet
        '''

        hp = False
        dev_specific = False
        telnet = False
        if ":" in ip_addr:
            type_list = ip_addr.split(":")
            ip_addr = type_list[0]
            for x in range(1, len(type_list)):
                var = type_list[x]
                var_list = var.split(",")
                var_type = var_list[0]
                if var_type == "model": hp = True
                if var_type == "conn": telnet = True
                if var_type == "user":
                    dev_specific = True
                    dev_username = var_list[1]
                    dev_password = var_list[2]
                    dev_enable = False
                try:
                    dev_enable = var_list[3]
                except IndexError:
                    pass
                    #ok no enable

        '''
        Open the SSH Connection with some error handling
        '''

        print_flush("Establishing connection to %-15s > " % (ip_addr))

        username = input_username
        password = input_password
        enable = ""

        if dev_specific:
            username = dev_username
            password = dev_password
            enable = dev_enable

        if not telnet:
            try:
                ssh.connect(ip_addr, username=username, password=password, timeout=8)
            except paramiko.ssh_exception.AuthenticationException:
                print "Authentication failed (SSH)."
                status_update(cust_dir, ip_addr, "", "*** Authentication failed. ***")
                continue
            except socket.error:
                print "Could not connect (SSH)."
                status_update(cust_dir, ip_addr, "", "*** Connection error (SSH). ***")
                continue
        else:
            try:
                shell = telnetlib.Telnet(ip_addr, 23, 4)
            except socket.error:
                print "Could not connect (Telnet)."
                status_update(cust_dir, ip_addr, "", "*** Connection error (Telnet). ***")
                continue

            shell.read_very_eager()
            output = shell_send(username, 1, 500, shell, telnet)
            auth_failed = re.search(r"Login invalid", output)
            if auth_failed:
                print "Authentication failed (Telnet)."
                status_update(cust_dir, ip_addr, "", "*** Authentication failed. ***")
                continue

            output = shell_send(password, 1, 500, shell, telnet)
            auth_failed = re.search(r"Login invalid", output)
            if auth_failed:
                print "Authentication failed (Telnet)."
                status_update(cust_dir, ip_addr, "", "*** Authentication failed. ***")
                continue

        print_flush("[ Connection established ]")


        '''
        Automate!
        '''

        print_flush("[ Automating... ]")

        '''
        HP does not support exec_command so we will use an interactive session
        for HP devices for cisco we will use the 'cleaner' exec_command method
        '''

        if not hp and not enable and not telnet and len(cmd_list) == 1:
            # Cisco Device
            stdin, stdout, stderr = ssh.exec_command(cmd)
            cmd_output = stdout.read()
        else:
            # HP Device, or enable password, or telnet
            if not telnet:
                shell = ssh.invoke_shell(width=200, height=99999)

                # Strip MOTD
                output = shell.recv(2000)

            # Enable mode
            if enable:
                shell_send("enable 15", 1 , 1000, shell, telnet)
                shell_send(enable, 1, 1000, shell, telnet)

            # Press enter,turn off paging
            shell_send("", 1, 1000, shell, telnet)

            if hp:
                paging = "no page"
            else:
                paging = "term len 0"

            shell_send(paging, 1, 500, shell, telnet)

            for cmd_loop in cmd_list:
                cmd_output = shell_send(cmd_loop, 6, 65535, shell, telnet)
                if hp:
                    cmd_output = clean_ansi(cmd_output)
                if cmd != "show run":
                    print_flush("[ " + cmd_loop + " ]")
                    update_cmd_log(cust_dir, ip_addr, cmd_output)

            shell.close()

        if cmd == "show run":
            # Use regex to find the hostname in the config
            try:
                hostname = get_hostname(cmd_output) + ".txt"
            except TypeError:
                hostname = ".txt"

            if hostname == ".txt":
                print " !!! Could not determine the hostname. !!!"
                status_update(cust_dir, ip_addr, "", "*** Could not discover the hostname. ***")
                continue


            '''
            Store the config
            '''

            filename = "".join([cust_dir, "/", hostname])

            print_flush("[ Storing the config as %s ]" % (filename))

            fileh = open(filename, "wb")
            fileh.write(cmd_output)
            fileh.close()

            status_update(cust_dir, ip_addr, hostname, "Completed.")

        print

        '''
        End of main program Loop.
        Repeat for each IP address in the customer info file
        '''

    '''
    All done!
    '''

    print "\nAutomation complete.  Please check the file timestamps and file contents then upload configs to Atlas.\n"
