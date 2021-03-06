#
# https://github.com/sperka/lusheeta
#

import logging
import os
import time
import utils

from ansible_mgr import AnsibleManager


class CloudCLI:
    def __init__(self, action, config, project_name):
        self.logger = logging.getLogger(__name__)

        self.preprocess_config(config)

        self.action = action
        self.config = config
        self.project_name = project_name

        # make sure "platform" is set in config
        if not config['platform']:
            config['platform'] = "openstack"

        platform_name = config['platform']
        platforms = utils.load_supported_platforms_config()
        assert (platform_name in platforms)

        platform = platforms[platform_name]

        # platform_settings_file check
        if 'platform_settings_file' in config:
            platform['settings_file'] = config['platform_settings_file']

        config['platform_settings'] = platform

        self.project_path = os.path.join(self.config['projects_dir'], self.config['project'])
        # save it to config, we'll need it later
        config['project_path'] = self.project_path

        self.logger.info("Instantiating class '%s' for platform '%s'", platform['class_name'], platform_name)
        _PLATFORM_CLASS = utils.import_platform_class(platform['package_name'], platform['module_name'],
                                                      platform['class_name'])
        self.platform_driver = _PLATFORM_CLASS(config, project_name)

    #

    #
    def run(self):
        """
        This method gets the action method of the current class and runs it.
        :return: None
        """
        action_fn = getattr(self, self.action)
        if not action_fn:
            self.logger.error("There is no %s action defined in this class. Quitting...", self.action)
            exit(1)

        action_fn()

    #

    #
    def create(self):
        """Create a cluster in the cloud
            Steps:
            1. Create a project folder
            2. Copy config item there
            3. Run driver's create_cluster method
        """
        # 1
        self.logger.info("Creating project dir '%s'", self.project_path)
        if os.path.exists(self.project_path):
            backup_path = os.path.join(self.config['projects_dir'],
                                       self.config['project'] + "-backup-" + time.strftime('%Y%m%d-%I%M%S'))
            self.logger.warn("Project directory exists with the same name ('%s'). Backing up content into '%s'",
                             self.project_path, backup_path)
            os.rename(self.project_path, backup_path)

        os.makedirs(self.project_path)

        # 2
        self.logger.debug("Saving current config to project dir...")
        utils.write_yaml_config(os.path.join(self.project_path, "config.yml"), self.config)

        # 3
        self.platform_driver.create_cluster()
        return

    #

    #
    def cleanup(self):
        """Cleanup the cluster from the cloud"""
        self.platform_driver.cleanup_cluster()

    #

    #
    def prepare_ansible(self):
        """Prepare required ansible files: inventory, ssh.config, ansible.cfg"""
        nodes = self.list_nodes()
        AnsibleManager(self.config, self.project_name).prepare_files(nodes)

    #

    #
    def run_ansible(self):
        """Run the ansible setup on the cluster in the cloud"""
        AnsibleManager(self.config, self.project_name).run_ansible_setup()
        return

    #

    #
    def list_nodes(self):
        return self.platform_driver.list_nodes()

    #

    #
    def preprocess_config(self, config):
        self.logger.info("Preprocessing config and settings necessary defaults...")
        config.setdefault('projects_dir', './projects')

        network = config.setdefault('network', {})
        network.setdefault('cidr', 'auto')
        network.setdefault('cidr_template', '10.X.100.0/24')
        network.setdefault('ext_net_name', 'ext-net')

        vm_mgmt = config.setdefault('vm_management', {})
        vm_mgmt.setdefault('default_image_name', 'Ubuntu 14.04.2_20150505')
        vm_mgmt.setdefault('default_vm_flavor', 'm1.medium')
        vm_mgmt.setdefault('hosts_startup_timeout', 600)
        vm_mgmt.setdefault('terminate_vm_poll', 5)

        hosts = config.setdefault('hosts', [])
        for host in hosts:
            host.setdefault('count', 1)
            cloud_vars = host.setdefault('cloud_vars', [])
            for cv in cloud_vars:
                cv.setdefault('index', 'all')

        ansible = config.setdefault('ansible', {})
        ansible.setdefault('ansible_dir', '../ansible/')
        ansible.setdefault('playbook', 'playbooks/setup_mesos_cluster.yml')
        ansible.setdefault('templates_path', './example/templates')
