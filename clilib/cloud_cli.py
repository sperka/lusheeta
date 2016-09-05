import logging
import os
import utils


class CloudCLI:
    def __init__(self, action, config, project_name):
        self.logger = logging.getLogger(__name__)

        self.action = action
        self.config = config
        self.project_name = project_name

        # make sure "platform" is set in config
        if not config['platform']:
            config['platform'] = "openstack"

        selected_platform = config['platform']

        platforms = utils.load_supported_platforms_config()
        assert(selected_platform in platforms)

        self.logger.debug("Importing class '%s' for platform '%s'", platforms[selected_platform], selected_platform)

        _PLATFORM_CLASS = utils.import_platform_class(selected_platform, platforms[selected_platform])
        self.driver = _PLATFORM_CLASS(config, project_name)

    def run(self):
        action_fn = getattr(self, self.action)
        action_fn()

    def create(self):
        """Create a cluster in the cloud
            Steps:
            1. Create a project folder
            2. Copy config item there
            3. Run driver's create_cluster method
        """
        # 1
        project_path = os.path.join(self.config['projects_dir'], self.config['project'])
        if not os.path.exists(project_path):
            os.makedirs(project_path)

        # 2
        utils.write_yaml_config(os.path.join(project_path, "config.yml"), self.config)

        # 3
        self.driver.create_cluster()
        return

    def cleanup(self):
        """Cleanup the cluster from the cloud"""
        self.driver.cleanup()
        return

    def prepare_ansible(self):
        """Prepare required ansible files: inventory, ssh.config, ansible.cfg"""
        return

    def run_ansible(self):
        """Run the ansible setup on the cluster in the cloud"""
        return
