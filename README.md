# ansible-openitcockpit-inventory

Provides a dynamic inventory from openITCOCKPIT of all satellites and the master server.

## Configuration

You can place the configuration under /etc/ansible/openitcockpit.ini, ~/.ansible/openitcockpit.ini or ./openitcockpit.ini

```
[openitcockpit]
url = https://127.0.0.1
username = you@example.com
password = somesecret
ldap = False
master_hostname = localhost
master_address = 127.0.0.1
validate_certs = False
```

If "master_address" is set to 127.0.0.1, ansible_connection will be set to local.

This script will always return the inventory data for the master server.


## Run

```bash
ansible-playbook -i openitcockpit.py site.yml
```
