import logging

from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver


class OpenstackDriver:
    def __init__(self, config, project_name):
        self.logger = logging.getLogger(__name__)

        self.config = config
        self.project_name = project_name
        Openstack = get_driver(Provider.OPENSTACK)
        # self.driver = Openstack()

    def create_cluster(self):
        self.logger.debug("Creating new cluster for project '%s'...", self.project_name)

    def cleanup_cluster(self):
        self.logger.debug("Cleaning up cluster for project '%s'", self.project_name)
