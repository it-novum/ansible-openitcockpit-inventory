#!/usr/bin/env python3

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
    exit_fail('Please install the python requests library, "apt-get install python3-requests" on debian/ubuntu')

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
        self.master_hostname = cfg.get('openitcockpit', 'master_hostname')
        self.master_address = cfg.get('openitcockpit', 'master_address')
        self.validate_certs = cfg.getboolean('openitcockpit', 'validate_certs')

        try:
            self.apikey = cfg.get('openitcockpit', 'apikey')
        except (NoSectionError, NoOptionError):
            exit_fail("Please specify apikey in the configuration file")


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
        self.groups['openitcockpit_main'] = [self.config.master_hostname]

        try:
            sat_request = requests.get(self.config.url + '/distribute_module/satellites/index.json',
                                       verify=self.config.validate_certs,
                                       params={'angular': 'true'},
                                       headers={'Authorization': 'X-OITC-API {}'.format(self.config.apikey)})

            if sat_request.status_code == 200:
                self.groups['openitcockpit_satellite'] = []
                try:
                    for sat in sat_request.json()['all_satellites']:
                        sat['ansible_host'] = sat['address']
                        try:
                            sat['timezone']
                        except KeyError:
                            sat['timezone'] = None
                        self.hosts[sat['name']] = sat
                        self.groups['openitcockpit'].append(sat['name'])
                        self.groups['openitcockpit_satellite'].append(sat['name'])
                except Exception as e:
                    print('Warning: There was an error parsing the output of the openitcockpit api\n{}'.format(str(e)))
                    raise
            else:
                print('Warning: API returned HTTP {}. Please check the openitcockpit server or credentials.'.format(sat_request.status_code))

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
