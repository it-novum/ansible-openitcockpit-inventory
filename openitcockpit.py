#!/usr/bin/env python

from __future__ import print_function

import os
import sys


def exit_fail(msg, exit_code=1):
    print(msg, file=sys.stderr)
    sys.exit(1)


try:
    from configparser import ConfigParser, NoSectionError, NoOptionError
except ImportError:
    from ConfigParser import ConfigParser, NoSectionError, NoOptionError
import json


try:
    import urllib3
    urllib3.disable_warnings()
except:
    pass

try:
    import requests
except ImportError:
    exit_fail('Please install the python requests library, "apt-get install python-requests" on debian/ubuntu')


class Configuration(object):

    def __init__(self):
        cfg = ConfigParser({
            'url': 'https://127.0.0.1',
            'ldap': 'False',
            'master_hostname': 'localhost',
            'master_address': '127.0.0.1',
            'validate_certs': 'False',
        })
        cfg.add_section('openitcockpit')
        read = cfg.read(['/etc/ansible/openitcockpit.ini',
                         os.path.expanduser('~/.ansible/openitcockpit.ini'),
                         'openitcockpit.ini'])
        if len(read) < 1:
            exit_fail('Could not find any configuration file')
        self.url = cfg.get('openitcockpit', 'url')
        self.ldap = cfg.getboolean('openitcockpit', 'ldap')
        self.master_hostname = cfg.get('openitcockpit', 'master_hostname')
        self.master_address = cfg.get('openitcockpit', 'master_address')
        self.validate_certs = cfg.getboolean('openitcockpit', 'validate_certs')

        try:
            self.username = cfg.get('openitcockpit', 'username')
            self.password = cfg.get('openitcockpit', 'password')
        except (NoSectionError, NoOptionError):
            exit_fail("Please specify username and password in the configuration file")

    def get_auth_data(self):
        if self.ldap:
            return {
                'data[LoginUser][auth_method]': 'ldap',
                'data[LoginUser][samaccountname]': self.username,
                'data[LoginUser][password]': self.password,
            }
        else:
            return {
                'data[LoginUser][auth_method]': 'session',
                'data[LoginUser][email]': self.username,
                'data[LoginUser][password]': self.password,
            }


class Inventory(object):

    def __init__(self, config):
        self.config = config
        self.hosts = {}
        self.groups = {}
        self.fetch_satellites()

    def fetch_satellites(self):
        master_address = self.config.master_address
        if master_address is None:
            master_address = self.config.master_hostname

        self.hosts[self.config.master_hostname] = {
            'address': master_address,
            'ansible_host': master_address,
        }
        if master_address == '127.0.0.1':
            self.hosts[self.config.master_hostname]['ansible_connection'] = 'local'
        self.groups['openitcockpit'] = [self.config.master_hostname]
        self.groups['oitc-master'] = [self.config.master_hostname]

        try:
            login_request = requests.post(self.config.url + '/login/login.json', 
                                        self.config.get_auth_data(),
                                        verify=self.config.validate_certs)

            if login_request.status_code != 200 or login_request.json()['message'] != 'Login successful':
                exit_fail('Login failed')

            sat_request = requests.get(self.config.url + '/distribute_module/satellites.json',
                                       cookies=login_request.cookies,
                                       verify=self.config.validate_certs)

            if sat_request.status_code == 200:
                self.groups['oitc-satellite'] = []
                for sat_data in sat_request.json()['all_satelittes']:
                    sat = sat_data['Satellite']
                    self.hosts[sat['name']] = {
                        'address': sat['address'],
                        'ansible_host': sat['address'],
                        'timezone': sat['timezone'],
                        'container': sat['container'],
                    }
                    self.groups['oitc-satellite'].append(sat['name'])

        except requests.exceptions.RequestException as e:
            print('Warning: Could not fetch satellite data\n{}'.format(str(e)), file=sys.stderr)

    def json(self):
        data = self.groups
        data['_meta'] = {
            'hostvars': self.hosts,
        }
        return json.dumps(data)


if __name__ == '__main__':
    if len(sys.argv) >= 2 and sys.argv[1] == '--list':
        print(Inventory(Configuration()).json())
