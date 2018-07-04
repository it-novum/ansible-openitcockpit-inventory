#!/usr/bin/env python

from __future__ import print_function

import os
import sys
import json


def exit_fail(msg, exit_code=1):
    print(msg, file=sys.stderr)
    sys.exit(exit_code)


try:
    from configparser import ConfigParser, NoSectionError, NoOptionError
except ImportError:
    from ConfigParser import ConfigParser, NoSectionError, NoOptionError

try:
    import requests
except ImportError:
    exit_fail('Please install the python requests library, "apt-get install python-requests" on debian/ubuntu')

try:
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
except:
    pass

try:
    import argparse
except ImportError:
    exit_fail('Please install the argparse package, "apt-get install python-argparse" on debian/ubuntu')


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
                         'openitcockpit.ini',
                         os.path.join(os.path.dirname(os.path.realpath(__file__)), 'openitcockpit.ini')])
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
                try:
                    for sat_data in sat_request.json()['satellites']:
                        sat = sat_data['Satellite']
                        host_data = {
                            'address': sat['address'],
                            'ansible_host': sat['address'],
                            'container': sat['container'],
                        }
                        try:
                            host_data['timezone'] = sat['timezone']
                        except KeyError:
                            host_data['timezone'] = None
                        self.hosts[sat['name']] = host_data
                        self.groups['openitcockpit'].append(sat['name'])
                        self.groups['oitc-satellite'].append(sat['name'])
                except Exception as e:
                    print('Warning: There was an error parsing the output of the openitcockpit api\n{}'.format(str(e)))
            else:
                print('Warning: API did not return HTTP 200. Please check the openitcockpit server.')

        except requests.exceptions.RequestException as e:
            print('Warning: Could not fetch satellite data\n{}'.format(str(e)), file=sys.stderr)

    def json(self, host=None):
        if host:
            try:
                data = self.hosts[host]
            except KeyError:
                data = {}
        else:
            data = self.groups
            data['_meta'] = {
                'hostvars': self.hosts,
            }
        return json.dumps(data)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description='This script creates a dynamic inventory for ansible from openitcockpit')
    p.add_argument('--list', action='store_true', default=False)
    p.add_argument('--host', default=None)
    args = p.parse_args()
    inv = Inventory(Configuration())

    if args.list:
        print(inv.json())
    elif args.host is not None:
        print(inv.json(host=args.host))
