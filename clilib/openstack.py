import logging
import utils
from pprint import pprint

from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver


class OpenstackDriver:
    def __init__(self, config, project_name):
        self.logger = logging.getLogger(__name__)

        self.config = config
        self.project_name = project_name

        openstack_settings = utils.load_yaml_config(config['platform_settings'])
        Openstack = get_driver(Provider.OPENSTACK)
        self.driver = Openstack(openstack_settings['username'], openstack_settings['password'],
                                ex_tenant_name=openstack_settings['project_name'],
                                ex_force_auth_url=openstack_settings['auth_url'],
                                ex_force_auth_version='2.0_password',
                                ex_force_service_region=openstack_settings['region_name'])

        # setup vars
        self._ssh_key = self.project_name+"_ssh"
        self._vm_prefix = self.project_name
        self._network_name = self.project_name+"_network"
        self._sec_group_name = self.project_name+"_secgroup"

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
        self.logger.debug("Creating new cluster for project '%s'...", self.project_name)

        # nodes = self.driver.list_nodes()
        # pprint(nodes)

        security_group = self.create_security_group()

        # self.cleanup_cluster()

    def cleanup_cluster(self):
        self.logger.debug("Cleaning up cluster for project '%s'", self.project_name)

        security_group = self.get_security_group();
        if security_group:
            self.driver.ex_delete_security_group(security_group)
        else:
            self.logger.warn("Security group '%s' was not found. Skipping...", self._sec_group_name)

    def get_security_group(self):
        """
        Retrieves the security group that belongs to the project.
        :return: The security group that belongs to the project or if it doesn't exists, None
        """
        all_security_groups = self.driver.ex_list_security_groups()
        proj_security_group = None
        for sec_group in all_security_groups:
            if sec_group.name == self._sec_group_name:
                proj_security_group = sec_group
                break
        return proj_security_group

    def create_security_group(self):
        security_group = self.get_security_group()
        if not security_group:
            security_group = self.driver.ex_create_security_group(self._sec_group_name,
                                                                  "Security group for project '" +self.project_name+"'")
        else:
            self.logger.warn("A security group with the name '%s' already exists!"
                             "Be sure you used a unique project name!"
                             "Cluster creation doesn't continue. Quitting...", self._sec_group_name)

        return security_group

