import logging
import utils
# from pprint import pprint

from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver

from openstack import connection


class OpenStackDriver:
    def __init__(self, config, project_name):
        self.logger = logging.getLogger(__name__)

        self.config = config
        self.project_name = project_name

        self.logger.debug("Loading openstack yaml config '%s'", config['platform_settings'])
        openstack_settings = utils.load_yaml_config(config['platform_settings'])

        self.driver = get_driver(Provider.OPENSTACK)(openstack_settings['username'], openstack_settings['password'],
                                                     ex_tenant_name=openstack_settings['project_name'],
                                                     ex_force_auth_url=openstack_settings['libcloud_auth_url'],
                                                     ex_force_auth_version='2.0_password',
                                                     ex_force_service_region=openstack_settings['region_name'])

        auth_args = {
            'auth_url': openstack_settings['openstacksdk_auth_url'],
            'project_name': openstack_settings['project_name'],
            'username': openstack_settings['username'],
            'password': openstack_settings['password']
        }
        conn = connection.Connection(**auth_args)
        self.network_driver = conn.network

        # setup vars
        self._ssh_key = self.project_name + "_ssh"
        self._vm_prefix = self.project_name
        self._network_name = self.project_name + "_network"
        self._subnet_name = self._network_name + "_subnet"
        self._router_name = self._network_name + "_router"
        self._sec_group_name = self.project_name + "_secgroup"

    def create_cluster(self):
        """
        Creates the cluster on the OpenStack cloud.

        1. Create security group with default rules
        2. Create network
        3. Create subnet
        4. Create router
        5. Set router gateway to ext-net
        6. Add router interface (router - subnet)
        """
        # TEMP
        self.cleanup_cluster()

        self.logger.info("Creating new cluster for project '%s'...", self.project_name)

        self.create_security_group()
        self.create_network()

    def cleanup_cluster(self):
        """
        Cleans up a cluster on the OpenStack cloud.

        1. Disassociate floating ips
        2. Terminate VMs
        3. Cleanup ssh key-pair
        4. Cleanup network
        5. Cleanup security group
        6. Cleanup free floating ips

        :return:
        """
        self.logger.debug("Cleaning up cluster for project '%s'", self.project_name)

        self.cleanup_network()
        self.cleanup_security_group()

    def get_security_group(self):
        """
        Retrieves the security group that belongs to the project.

        :return: The security group that belongs to the project or if it doesn't exists, None
        :rtype: :class:`OpenStackSecurityGroup`
        """
        all_security_groups = self.driver.ex_list_security_groups()
        sg = None
        for sec_group in all_security_groups:
            if sec_group.name == self._sec_group_name:
                sg = sec_group
                break
        return sg

    def create_security_group(self):
        """
        Creates security group for the project and its default rules.

        :return: The new security group object
        :rtype: :class:`OpenStackSecurityGroup`
        """
        sg = self.get_security_group()
        if not sg:
            self.logger.info("Creating security group '%s'", self._sec_group_name)
            sg = self.driver.ex_create_security_group(
                self._sec_group_name, "Security group for project '" + self.project_name + "'")

            self.logger.info("Creating security group rules for '%s'", self._sec_group_name)
            self.driver.ex_create_security_group_rule(sg, 'tcp', 1, 65535, source_security_group=sg)
            self.driver.ex_create_security_group_rule(sg, 'udp', 1, 65535, source_security_group=sg)
        else:
            self.logger.warn("A security group with the name '%s' already exists! "
                             "Be sure you used a unique project name! "
                             "Cluster creation doesn't continue. Quitting...", self._sec_group_name)
            exit(1)

        return sg

    def cleanup_security_group(self):
        sg = self.get_security_group()
        if sg:
            self.logger.info("Cleaning up security group rules for '%s'", self._sec_group_name)
            for rule in sg.rules:
                self.driver.ex_delete_security_group_rule(rule)
            self.logger.info("Cleaning up security group '%s'", self._sec_group_name)
            self.driver.ex_delete_security_group(sg)
        else:
            self.logger.warn("Security group '%s' was not found. Skipping...", self._sec_group_name)

    def get_network(self):
        networks = self.driver.ex_list_networks()
        for network in networks:
            if network.name == self._network_name:
                return network
        return None

    def create_network(self):

        network = self.get_network()
        if not network:
            self.logger.info("Creating network '%s'", self._network_name)
            cidr = self.config['network_cidr']

            if cidr == "auto":
                self.logger.debug("CIDR not set explicitly, generating next CIDR based on 'network_cidr_template'")
                cidr = self.get_next_cidr()
                self.logger.debug("Next CIDR: '%s'", cidr)

            # self.driver.ex_create_network(self._network_name, cidr)
            network = self.network_driver.create_network(name=self._network_name)
            subnet = self.network_driver.create_subnet(
                name=self._subnet_name,
                network_id=network.id,
                ip_version="4",
                cidr=cidr,
                gateway_ip=cidr.replace('.0/24', '.1')
            )
            router = self.network_driver.create_router(name=self._router_name)

        else:
            self.logger.warn("A network with the name '%s' already exists!"
                             "Be sure you used a unique project name! "
                             "Cluster creation doesn't continue. Quitting...", self._network_name)

    def get_next_cidr(self):
        cidr_template = self.config['network_cidr_template']
        subnets = list(self.network_driver.subnets())

        cidr_ctr = len(subnets)
        search_next_cidr = True

        while search_next_cidr:
            cidr_ctr += 1
            cidr = cidr_template.replace('X', str(cidr_ctr))
            search_next_cidr = any(subnet.cidr == cidr for subnet in subnets)

        return cidr_template.replace('X', str(cidr_ctr))

    def cleanup_network(self):
        router = self.network_driver.find_router(self._router_name)
        if router:
            self.network_driver.delete_router(router)
        else:
            self.logger.warn("Router '%s' was not found. Skipping...", self._router_name)

        # network = self.get_network()
        network = self.network_driver.find_network(self._network_name)
        if network:
            # self.driver.ex_delete_network(network)
            self.logger.info("Cleaning up network '%s' and its subnet '%s'", self._network_name, self._subnet_name)
            for subnet in network.subnet_ids:
                self.network_driver.delete_subnet(subnet, ignore_missing=False)
            self.network_driver.delete_network(network, ignore_missing=False)
        else:
            self.logger.warn("Network '%s' was not found. Skipping...", self._network_name)