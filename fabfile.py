# -*- coding: utf-8 -*-
from time import sleep
from fabric.context_managers import lcd
from fabric.contrib.files import upload_template
from fabric.decorators import roles, parallel
from fabric.operations import put, run
from fabric.state import env
from fabric.tasks import execute


env.roledefs = {
    'mgm_nodes': {
        'hosts': ['10.211.55.36']
    },
    'data_nodes': {
        'hosts': ['10.211.55.37', '10.211.55.38']
    },
    'sql_nodes': {
        'hosts': ['10.211.55.39']
    }
}

# env.roledefs = {
#     'mgm_nodes': {
#         'hosts': ['210.122.7.220'],
#         'node_hosts': ['10.128.69.31']
#     },
#     'data_nodes': {
#         'hosts': ['210.122.7.219', '210.122.7.156'],
#         'node_hosts': ['10.128.69.27', '10.128.69.19']
#     },
#     'sql_nodes': {
#         'hosts': ['210.122.7.221'],
#         'node_hosts': ['10.128.69.35']
#     }
# }

# env.passwords = {
#     'root@210.122.7.220:22': '',
#     'root@210.122.7.219:22': '',
#     'root@210.122.7.156:22': '',
#     'root@210.122.7.221:22': '',
# }

env.user = 'root'
env.warn_only = True

def create_conf_files():
    configurations = []
    node_hosts = {}
    for node_type in ['mgm_nodes', 'data_nodes', 'sql_nodes']:
        node_hosts[node_type] = env.roledefs[node_type]['node_hosts'] if env.roledefs[node_type].get('node_hosts') else env.roledefs[node_type]['hosts']

    # configuation for config.ini
    configuration_1 = {}
    configuration_1['file'] = 'config.ini'
    configuration_1['replacements'] = {
        '<num_of_replicas>': str(len(node_hosts['data_nodes'])),
        '<mgm_node>': '',
        '<data_node>': '',
        '<sql_node>': ''
    }

    for host in node_hosts['mgm_nodes']:
        configuration_1['replacements']['<mgm_node>'] += "[ndb_mgmd]\nhostname=%s\ndatadir=/var/lib/mysql-cluster\n\n" % host

    for host in node_hosts['data_nodes']:
        configuration_1['replacements']['<data_node>'] += "[ndbd]\nhostname=%s\ndatadir=/usr/local/mysql/data\n\n" % host

    for host in node_hosts['sql_nodes']:
        configuration_1['replacements']['<sql_node>'] += "[mysqld]\nhostname=%s\n\n" % host

    configurations.append(configuration_1)

    # configuration for my.cnf
    configuration_2 = {}
    configuration_2['file'] = 'my.cnf'
    configuration_2['replacements'] = {'<mgm_node_ip>': node_hosts['mgm_nodes'][0]}
    configurations.append(configuration_2)

    for configuration in configurations:
        infile = open('confs/base/'+configuration['file'])
        outfile = open('confs/'+configuration['file'], 'w')

        for line in infile:
            for src, target in configuration['replacements'].iteritems():
                line = line.replace(src, target)
            outfile.write(line)

        infile.close()
        outfile.close()

def kill_and_run(process, command, num_of_attempts=3):
    run('pkill %s' % process)
    for i in range(num_of_attempts):
        sleep(5)
        if not run('pgrep -l %s' % process):
            run(command)
            break

@roles("mgm_nodes")
def setup_mgm_nodes():
    create_conf_files()
    put('scripts/mgmnode.sh', '/var/tmp')
    run('chmod +x /var/tmp/mgmnode.sh')
    run('/var/tmp/mgmnode.sh')
    put('confs/config.ini', '/var/lib/mysql-cluster')

@roles("data_nodes")
def setup_data_nodes():
    create_conf_files()
    put('confs/my.cnf', '/etc')
    put('scripts/datanode.sh', '/var/tmp')
    run('chmod +x /var/tmp/datanode.sh')
    run('/var/tmp/datanode.sh')

@roles("sql_nodes")
def setup_sql_nodes():
    create_conf_files()
    put('confs/my.cnf', '/etc')
    put('scripts/sqlnode.sh', '/var/tmp')
    run('chmod +x /var/tmp/sqlnode.sh')
    run('/var/tmp/sqlnode.sh')

@roles("mgm_nodes")
def start_mgm_nodes():
    run('ndb_mgm -e shutdown')
    kill_and_run('ndb_mgmd', '/usr/local/bin/ndb_mgmd -f /var/lib/mysql-cluster/config.ini --configdir=/var/lib/mysql-cluster --initial')

@roles("data_nodes")
def start_data_nodes():
    run('ndbd --initial')

@roles("sql_nodes")
def start_sql_nodes():
    kill_and_run('mysql', 'service mysql.server start')

def setup_mysql_cluster():
    execute(setup_mgm_nodes)
    execute(setup_data_nodes)
    execute(setup_sql_nodes)

def start_mysql_cluster():
    execute(start_mgm_nodes)
    execute(start_data_nodes)
    execute(start_sql_nodes)
