import logging
import os
import stat
import clilib.utils as utils
import time

from openstack import connection


class OpenStackDriver:
    cloud_images_dict = None
    flavors_dict = None
    ip_pools = None
    proj_network_cached = None
    ext_net_cached = None

    def __init__(self, config, project_name):
        self.logger = logging.getLogger(__name__)

        self.config = config
        self.project_name = project_name

        self.logger.debug("Loading openstack yaml config '%s'", config['platform_settings']['settings_file'])
        openstack_settings = utils.load_yaml_config(config['platform_settings']['settings_file'])

        auth_args = {
            'auth_url': openstack_settings['auth_url_base'],
            'project_name': openstack_settings['project_name'],
            'username': openstack_settings['username'],
            'password': openstack_settings['password']
        }
        conn = connection.Connection(**auth_args)
        self.network_api = conn.network
        self.compute_api = conn.compute
        self.cluster_api = conn.cluster
        self.identity_api = conn.identity

        # setup vars
        self._ssh_key = self.project_name + "_ssh"
        self._vm_prefix = self.project_name
        self._network_name = self.project_name + "_network"
        self._subnet_name = self._network_name + "_subnet"
        self._router_name = self._network_name + "_router"
        self._router_port_name = self._router_name + "_port"
        self._sec_group_name = self.project_name + "_secgroup"

    def create_cluster(self):
        """
        Creates the cluster on the OpenStack cloud.

        1. Create security group with default rules
        2. Create network, subnet, router, set router gateway to ext-net, add router interface (router - subnet)
        3. Create ssh key-pair in the cloud, then download
        4. Create VMs
        5. Create floating IPs and associate them
        6. Import ssh key-pair to bastion if exists
        """
        # TODO: check available resources
        # self.check_available_resources()

        # TEMP
        # self.cleanup_cluster()

        self.logger.info("Creating new cluster for project '%s'...", self.project_name)

        self.create_security_group()
        self.create_network()
        self.create_ssh_key_pair()
        self.create_vms()

        self.process_cloud_vars()

        self.logger.info("Cluster setup for project '%s' complete...", self.project_name)

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
        self.logger.info("Cleaning up cluster for project '%s'", self.project_name)

        self.disassociate_floating_ips()
        self.terminate_vms()
        self.cleanup_ssh_key_pair()
        self.cleanup_network()
        self.cleanup_security_group()

        self.logger.info("Cluster cleanup for project '%s' complete...", self.project_name)

    def check_available_resources(self):
        self.logger.warn("'check_available_resources' NOT IMPLEMENTED YET")

    def get_security_group(self, include_default=False):
        """
        Retrieves the security group that belongs to the project.

        :return: The security group that belongs to the project or if it doesn't exists, None
        :rtype: :class:`OpenStackSecurityGroup`
        """
        all_security_groups = self.network_api.security_groups()
        sg = None
        default = None
        for sec_group in all_security_groups:
            if include_default and sec_group.name == 'default':
                default = sec_group
                continue

            if sec_group.name == self._sec_group_name:
                sg = sec_group
                continue

        if include_default:
            return [default, sg]

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
            sg = self.network_api.create_security_group(name=self._sec_group_name,
                                                        description="Security group for project '" + self.project_name + "'")

            self.logger.info("Creating security group rules for '%s'", self._sec_group_name)

            self.network_api.create_security_group_rule(direction="ingress",
                                                        ether_type="IPv4",
                                                        port_range_min=1, port_range_max=65535, protocol="tcp",
                                                        security_group_id=sg.id)

            self.network_api.create_security_group_rule(direction="egress",
                                                        ether_type="IPv4",
                                                        port_range_min=1, port_range_max=65535, protocol="tcp",
                                                        security_group_id=sg.id)

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
            for rule in sg.security_group_rules:
                self.network_api.delete_security_group_rule(rule)
            self.logger.info("Cleaning up security group '%s'", self._sec_group_name)
            self.network_api.delete_security_group(sg)
        else:
            self.logger.warn("Security group '%s' was not found. Skipping...", self._sec_group_name)

    def get_proj_network(self):
        if not OpenStackDriver.proj_network_cached:
            OpenStackDriver.proj_network_cached = self.network_api.find_network(name_or_id=self._network_name)
        return OpenStackDriver.proj_network_cached

    def get_ext_net(self):
        if not OpenStackDriver.ext_net_cached:
            OpenStackDriver.ext_net_cached = self.network_api.find_network(name_or_id=self.config['network']['ext_net_name'])
        return OpenStackDriver.ext_net_cached

    def create_network(self):

        network = self.get_proj_network()
        if not network:
            self.logger.info("Creating network '%s'", self._network_name)
            cidr = self.config['network']['cidr']

            if cidr == "auto":
                self.logger.debug("CIDR not set explicitly, generating next CIDR based on 'network.cidr_template'")
                cidr = self.get_next_cidr()
                self.logger.debug("Next CIDR: '%s'", cidr)

            network = self.network_api.create_network(name=self._network_name)
            gateway_ip = cidr.replace('.0/24', '.1')
            subnet = self.network_api.create_subnet(
                name=self._subnet_name,
                network_id=network.id,
                ip_version="4",
                cidr=cidr,
                gateway_ip=gateway_ip
            )
            ext_net_network = self.get_ext_net()
            if ext_net_network:
                router = self.network_api.create_router(
                    name=self._router_name,
                    external_gateway_info={'network_id': ext_net_network.id}
                )
                port = self.network_api.create_port(name=self._router_port_name, network_id=network.id,
                                                    fixed_ips=[{"subnet_id": subnet.id, "ip_address": gateway_ip}])
                self.network_api.add_interface_to_router(router, subnet_id=subnet.id, port_id=port.id)
            else:
                self.logger.error("External gateway '%s' not found. Can't connect router to the external network...",
                                  self.config['network']['ext_net_name'])

        else:
            self.logger.warn("A network with the name '%s' already exists!"
                             "Be sure you used a unique project name! "
                             "Cluster creation doesn't continue. Quitting...", self._network_name)

    def get_next_cidr(self):
        cidr_template = self.config['network']['cidr_template']
        subnets = list(self.network_api.subnets())

        cidr_ctr = len(subnets)
        search_next_cidr = True

        while search_next_cidr:
            cidr_ctr += 1
            cidr = cidr_template.replace('X', str(cidr_ctr))
            search_next_cidr = any(subnet.cidr == cidr for subnet in subnets)

        return cidr_template.replace('X', str(cidr_ctr))

    def cleanup_network(self):
        self.logger.info("Cleaning up network %s", self._network_name)

        router = self.network_api.find_router(self._router_name)
        network = self.get_proj_network()
        subnet_id = None
        if network and len(network.subnet_ids):
            subnet_id = network.subnet_ids[0]

        if router:
            if subnet_id:
                from openstack.exceptions import NotFoundException
                ports = self.network_api.ports(subnet_id=subnet_id)
                for port in ports:
                    try:
                        self.network_api.remove_interface_from_router(router, subnet_id, port.id)
                    except NotFoundException as e:
                        self.logger.error("Problem with removing interface from router: %s", e.message)

                    # and remove port as well
                    if not port.device_owner.startswith('network:'):
                        self.network_api.delete_port(port)
            else:
                self.logger.warn("Subnet and its ports not found. Skipping...")

            # remove router
            self.network_api.delete_router(router)
        else:
            if subnet_id:
                # if router already removed but some ports are still around...
                ports = self.network_api.ports(subnet_id=subnet_id)
                for port in ports:
                    if not port.device_owner.startswith('network:'):
                        self.network_api.delete_port(port)

            self.logger.warn("Router '%s' was not found. Skipping...", self._router_name)

        if network:
            self.logger.info("Cleaning up network '%s' and its subnet '%s'", self._network_name, self._subnet_name)
            for subnet in network.subnet_ids:
                self.network_api.delete_subnet(subnet, ignore_missing=False)
            self.network_api.delete_network(network, ignore_missing=False)
        else:
            self.logger.warn("Network '%s' was not found. Skipping...", self._network_name)

    def create_ssh_key_pair(self):
        project_path = os.path.join(self.config['projects_dir'], self.config['project'])

        kp = self.compute_api.find_keypair(name_or_id=self._ssh_key)
        if not kp:
            self.logger.info("Creating ssh key pair %s and saving to %s", self._ssh_key, project_path)

            key_pair = self.compute_api.create_keypair(name=self._ssh_key)
            utils.save_string_to_file(key_pair.private_key, os.path.join(project_path, self._ssh_key),
                                      chmod=(stat.S_IRUSR | stat.S_IWUSR))
            utils.save_string_to_file(key_pair.public_key, os.path.join(project_path, self._ssh_key + ".pub"))

    def cleanup_ssh_key_pair(self):
        self.logger.info("Cleaning up ssh key pair %s", self._ssh_key)

        key_pair = self.compute_api.find_keypair(name_or_id=self._ssh_key)

        if key_pair:
            self.compute_api.delete_keypair(key_pair)
        else:
            self.logger.warn("SSH key pair %s not found. Skipping...", self._ssh_key)

    def create_vms(self):
        self.logger.info("Creating VMs...")

        security_groups = self.get_security_group(include_default=True)
        if not security_groups:
            self.logger.error("Error retrieving security group %s when creating nodes. Quitting...",
                              self._sec_group_name)
            exit(1)

        network = self.get_proj_network()
        if not network:
            self.logger.error("Error retrieving network %s when creating nodes. Quitting...", self._network_name)
            exit(1)
        network_ids = [{'uuid': network.id}]

        default_image = self.get_image(self.config['vm_management']['default_image_name'])

        hosts = self.config['hosts']
        new_nodes = []

        self.logger.debug("Waiting for new nodes to start up...")
        start_time = time.time()

        for host in hosts:
            cnt = host['count']

            for i in range(0, cnt):
                host_name = self.project_name + "-" + host['name']
                if cnt > 1:
                    host_name = host_name + "_" + str(i + 1)

                flavor_name = host.get('vm_flavor', self.config['vm_management']['default_vm_flavor'])
                flavor = self.get_flavor(flavor_name)
                if not flavor:
                    self.logger.error("Flavor '%s' doesn't exist. Skipping creating host '%s'", flavor_name, host_name)
                    continue

                image = default_image
                if 'image' in host:
                    image = self.get_image(host['image_name'])

                self.logger.info("Creating VM: %s", host_name)

                node = self.compute_api.create_server(
                    name=host_name,
                    flavor_id=flavor.id,
                    image_id=image.id,
                    key_name=self._ssh_key,
                    networks=network_ids
                )

                new_nodes.append(node)
                self.compute_api.wait_for_server(node)

                for sg in security_groups:
                    self.compute_api.add_security_group_to_server(node, sg)

        self.logger.info("Startup for %s nodes took %s seconds", len(new_nodes), (time.time() - start_time))

    def get_image(self, name):
        if not OpenStackDriver.cloud_images_dict:
            cloud_images = self.compute_api.images()
            if not cloud_images:
                self.logger.error("Error retrieving image list. Quitting...")
                exit(1)
            OpenStackDriver.cloud_images_dict = dict((x.name, x) for x in cloud_images)

        return OpenStackDriver.cloud_images_dict[name]

    def get_flavor(self, name):
        if not OpenStackDriver.flavors_dict:
            flavors_list = self.compute_api.flavors()
            if not flavors_list:
                self.logger.error("Error retrieving flavors. Quitting...")
                exit(1)
            OpenStackDriver.flavors_dict = dict((x.name, x) for x in flavors_list)

        return OpenStackDriver.flavors_dict[name]

    def terminate_vms(self):
        self.logger.info("Terminating VMs...")
        nodes = self.compute_api.servers()
        node_names = []

        for host in self.config['hosts']:
            cnt = host['count']
            for i in range(0, cnt):
                host_name = self.project_name + "-" + host['name']
                if cnt > 1:
                    host_name = host_name + "_" + str(i + 1)
                node_names.append(host_name)

        for node in nodes:
            if node.name in node_names:
                self.logger.info("Terminating VM: %s", node.name)
                self.compute_api.delete_server(node.id)

        # need to wait until termination process finishes
        self.logger.debug("Waiting for nodes to terminate...")
        wait_more = True
        while wait_more:
            self.logger.debug("Still waiting for nodes to terminate...")
            time.sleep(self.config['vm_management']['terminate_vm_poll'])
            nodes = self.compute_api.servers()
            wait_more = any(node.name in node_names for node in nodes)

        self.logger.debug("All nodes terminated...")

    def process_cloud_vars(self):
        nodes = list(self.compute_api.servers())

        for host in self.config['hosts']:
            cnt = host['count']

            if 'cloud_vars' in host:
                for cloud_var in host['cloud_vars']:
                    index = 'all'
                    if 'index' in cloud_var:
                        index = cloud_var['index']

                    if 'assignPublicIP' in cloud_var:
                        if cloud_var['assignPublicIP']:
                            self.create_and_assign_floating_ip(host, index, nodes)

    def create_and_assign_floating_ip(self, host, index, nodes):
        def pick_node(_nodes, name):
            for n in _nodes:
                if n.name == name:
                    return n

        ext_net = self.get_ext_net()

        cnt = host['count']
        if index == 'all' or index == 'counter':
            index = range(0, cnt)
        else:
            index = range(index, index + 1)

        for i in index:
            host_name = self.project_name + "-" + host['name']
            if cnt > 1:
                host_name = host_name + "_" + str(i + 1)
            floating_ip = self.network_api.create_ip(description="Floating IP for " + host_name,
                                                     floating_network_id=ext_net.id)

            node = pick_node(nodes, host_name)
            self.logger.info("Creating floating ip and assigning to node %s", host_name)
            self.compute_api.add_floating_ip_to_server(node, floating_ip.floating_ip_address)

    def iterate_through_hosts(self, action):
        for host in self.config['hosts']:
            cnt = host['count']

            for i in range(0, cnt):
                host_name = self.project_name + "-" + host['name']
                if cnt > 1:
                    host_name = host_name + "_" + str(i + 1)

                action(host_name)

    def disassociate_floating_ips(self):
        self.logger.info("Disassociating public ips from VMs...")

        nodes = self.compute_api.servers()
        node_names = []
        for host in self.config['hosts']:
            cnt = host['count']

            for i in range(0, cnt):
                host_name = self.project_name + "-" + host['name']
                if cnt > 1:
                    host_name = host_name + "_" + str(i + 1)
                node_names.append(host_name)

        floating_ips = self.network_api.ips()
        floating_ips_dict = dict((x.floating_ip_address, x) for x in floating_ips)

        for node in nodes:
            if node.name in node_names:
                if self._network_name in node.addresses and node.addresses[self._network_name]:
                    for ip_to_detach in node.addresses[self._network_name]:
                        if ip_to_detach['OS-EXT-IPS:type'] != 'fixed':
                            self.logger.info("Detaching ip '%s' from node '%s'", ip_to_detach['addr'], node.name)
                            self.compute_api.remove_floating_ip_from_server(node, ip_to_detach['addr'])

                            self.logger.info("Deleting floating ip '%s'", ip_to_detach)
                            self.network_api.delete_ip(floating_ips_dict[ip_to_detach['addr']])

    def list_nodes(self):
        return list(self.compute_api.servers())
