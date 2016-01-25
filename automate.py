#!/usr/bin/env python

'''
This module presents a menu system allowing the user to select from a list of autimation tasks.
The list will start small with new additions added as the need arises.  This module uses netmiko
by Kirk Byers to handle SSH connectivity.

The input file will use a list of IP addresses with various defaults if specific details are not present.
The user will be prompted for credentials which will be used for the menu.

To do:

    Call netmiko in a modular way so that telnet connectivity can be added as required

Automation Tasks:

    Connection check - This option will test connectivity to all devices to a) validate SSH connectivity
    and b) test access credentials

    IP host table - This option will connect to all devices and retrieve the hostname, interface IP addresses
    and BGP neighbors that are members of AS 39097 (Azzurri). These IP's will be used to build name to IP
    mapping tables to make traceroutes easier to read

'''


import netmiko
import paramiko
import getpass
import telnetlib
import sys
import re


'''
Functions
'''

def get_defaults():

    '''
    this function reads in defaults for the user inputs customer dir and user name
    tools.pref should exist in the same directory as the tools.

    tools.pref is not required.

    sample tools.pref:

    acme-ltd.info
    nicko

    '''

    try:
        defaults_fileh = open("tools.pref")
    except IOError:
        return ['', '']

    prefs = defaults_fileh.read().split()
    defaults_fileh.close()

    try:
        if prefs[1]:
            pass
    except IndexError:
        prefs.append('')

    return prefs


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


'''
Main module loop
'''

if __name__ == "__main__":


    # read defaults
    (def_cust, def_user) = get_defaults()

    '''
    Prompt the user for customer info file and SSH credentials
    '''

    while True:

        print

        cust = raw_input_def("Input the customer info file [%s]: " % def_cust, def_cust)
        input_username = raw_input_def("Input SSH username [%s]: " % def_user, def_user)
        input_password = getpass.getpass("Input SSH password: ")

        yesno = raw_input_def("\nAre these details correct (y/n) [y]:", 'y')
        yesno = yesno.lower()

        if yesno == "y":
            break

    while True:

        print "\n"
        print "============================="
        print "     Automation Toolkit"
        print "=============================\n\n\n"
        print ("Device input file [%s]\n\n" % cust)

        print "1. Connectivity Test"

        print "\n\n\n"

        menu_option = raw_input_def("Select item # from list above (1-1) [1]: ", '1')

        yesno = raw_input_def("\nAre you sure (y/n) [y]:", 'y')
        yesno = yesno.lower()

        if yesno == "y":
            break

    print


    '''
    Read the customer file to determine the folder and a list of IPs
    '''

    cust_fileh = open(cust)
    cust_dir = cust_fileh.readline().strip()
    ip_list = cust_fileh.readlines()
    cust_fileh.close()


    '''
    Main loop to read each IP and carry out the autmation function
    '''

    for ip_addr in ip_list:
        ip_addr = ip_addr.strip()

        '''
        Skip if ip_addr has been # out
        '''

        if '#' in ip_addr:
            print " Skipping %s" % (ip_addr.split("#")[1])
            #status_update(cust_dir, ip_addr.split("#")[1], "", "*** Skipped. ***")
            continue

        '''
        If the IP address contains a : then options have been added
        :model,hp
        :user,tempuser,pass123,enablepass - enablepass is optional
        :conn,telnet
        '''

        username = input_username
        password = input_password
        enable = False
        telnet = False
        model = 'cisco_ios'

        if ':' in ip_addr:

            type_list = ip_addr.split(':')
            ip_addr = type_list[0]

            for x in range(1, len(type_list)):

                var = type_list[x]
                var_list = var.split(',')
                var_type = var_list[0]

                if var_type == 'model':
                    model = 'hp'
                    try:
                        model = var_list[1]
                    except IndexError:
                        pass

                if var_type == 'conn': telnet = True

                if var_type == 'user':
                    username = var_list[1]
                    password = var_list[2]
                    enable = False
                try:
                    dev_enable = var_list[3]
                except IndexError:
                    pass
                    #ok no enable

        if menu_option == '1':

        # Perform connectivity check

            if not telnet:

                #print model
                #print ip_addr
                #print username
                #print password

                try:
                    device = netmiko.ConnectHandler(device_type=model, ip=ip_addr, username=username, password=password)

                except netmiko.ssh_exception.NetMikoAuthenticationException:
                    print ("Authentication failed for %s" % ip_addr)
                    continue

                except netmiko.ssh_exception.NetMikoTimeoutException:
                    print ("Connection to %s refused or timed out" % ip_addr)
                    continue

                except paramiko.ssh_exception.SSHException:
                    print ("Connection to %s refused or timed out" % ip_addr)
                    continue


                print ("Connection to %s successful\n" % ip_addr)
                device.disconnect()
