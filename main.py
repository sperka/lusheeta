#!/usr/bin/env python

import os
import json
import yaml
import argparse

class CloudCLI:
    def __init__(self, action="create", config=None, project_name):
        self.action = action
        self.config = config
        self.project_name = project_name

if __name__ == "__main__":
    with open("config/default.yml", 'r') as default_yaml_config_file:
        config = yaml.load(default_yaml_config_file)

    print(config)

    allowed_actions=["create", "cleanup", "prepare_ansible", "run_ansible"]

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="CPSWTNG Cloud CLI tool")
    parser.add_argument("-a", "--action", choices=allowed_actions, help="the action to do")
    parser.add_argument("-c", "--config", type=argparse.FileType('r'), help="path to the configuration file")
    parser.add_argument("-v", "--verbose", help="set verbosity mode", action="count")
    parser.add_argument("project", nargs=1, help="the name of the project")

    args = parser.parse_args()

    action = "create"
    if args.action:
        action = args.action

    config_file = "config/default.yml"
    if args.config:
        config_file = args.config

    verbose_level = args.verbose
    project_name = args.project

    cli = new CloudCLI(action, config, project_name)