#!/usr/bin/env python

import argparse
import logging
import clilib.utils as utils

from clilib.cloud_cli import CloudCLI


if __name__ == "__main__":
    allowed_actions = ["create", "cleanup", "prepare_ansible", "run_ansible"]

    # setup command line arguments
    parser = argparse.ArgumentParser(description="CPSWTNG Cloud CLI tool")
    parser.add_argument("-a", "--action", choices=allowed_actions, required=True, help="the action to do")
    parser.add_argument("-c", "--config", type=argparse.FileType('r'), help="path to the configuration file")
    parser.add_argument("-v", "--verbose", help="set verbosity mode", action="count")
    parser.add_argument("project", nargs=1, help="the name of the project")

    # parse command line args
    args = parser.parse_args()

    action = args.action
    config_file = "config/default.yml"
    if args.config:
        config_file = args.config
    cli_config = utils.load_yaml_config(config_file)
    verbose_level = args.verbose
    project_name = args.project[0]

    # setup logger
    logging.basicConfig(level=utils.get_log_level(verbose_level))
    logging.getLogger().addHandler(logging.FileHandler("cloud_cli.log"))
    logger = logging.getLogger(__name__)

    # overwrite config.project with the passed value (may be different)
    cli_config['project'] = project_name

    logger.info("Starting Lusheeta CLI...")
    logger.debug("Allowed actions for the CLI: %s", allowed_actions)
    logger.debug("Passed args:\t"
                 "action = '%s'\t"
                 "config_file = '%s'\t"
                 "verbose_level = '%s'\t"
                 "project_name = '%s'", action, config_file, verbose_level, project_name)

    cli = CloudCLI(action=action, config=cli_config, project_name=project_name)
    cli.run()
