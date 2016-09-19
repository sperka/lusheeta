import logging
import os
import utils
from jinja2 import Environment, FileSystemLoader

_SPACES = "   "


class AnsibleManager:
    def __init__(self, config, project_name):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.project_name = project_name

        templates_path = config['ansible'].get('templates_path')
        if templates_path:
            self.j2_env = Environment(loader=FileSystemLoader(templates_path), trim_blocks=True)
        else:
            self.logger.error("No ansible.templates_path set. Can't continue...")
            exit(1)

        self.substitution_rules = {
            'item_vars': {
                'ansible_host': 'substitute_ansible_host',
                'hostname': 'substitute_host_name'
            },
            'group_vars': {}
        }

    def prepare_files(self, cloud_nodes):
        ansible_settings = self.config['ansible']
        inventory_template_path = ansible_settings.get('inventory_template')
        if inventory_template_path:
            self._generate_inventory_file(cloud_nodes)
        else:
            self.logger.warn("ansible.inventory_template not set. Skipping inventory file generation...")

    def _generate_inventory_file(self, cloud_nodes):
        project_path = self.config['project_path']
        inventory_template = self.j2_env.get_template(self.config['ansible']['inventory_template'])

        hosts = self.config['hosts']

        template_vars = {}

        # iterate through all the the hosts defined
        for host in hosts:
            host_ansible_settings = host['ansible_settings']
            cnt = host['count']

            # each host 'count' times
            for i in range(0, cnt):
                host_name = self.project_name + "-" + host['name']
                inventory_host_name = host['name']
                if cnt > 1:
                    host_name += "_" + str(i + 1)
                    inventory_host_name += "_" + str(i + 1)

                # iterate through 'ansible_settings' array
                for ans_setting in host_ansible_settings:
                    # get the array of the hosts for the inventory group so that we can add more
                    inventory_group = template_vars.setdefault(ans_setting['ansible_group'], [])

                    # we'll generate the string based on this dict
                    inventory_item = {}

                    # check item_vars -- all 'count' entries will have these properties
                    item_vars = ans_setting.get('item_vars', [])
                    for item_var in item_vars:
                        for item_var_key in item_var:
                            sub_fn_name = self.substitution_rules['item_vars'].get(item_var_key)
                            if sub_fn_name:
                                sub_fn = getattr(self, sub_fn_name)
                                if not sub_fn:
                                    self.logger.warn(
                                        "%s method not found in the implementation as a substitution rule. Skipping...",
                                        sub_fn_name)
                                    continue

                                # make a copy and remove "additional" 'self' key in order to pass the dict
                                _locals = dict(locals())
                                del _locals['self']

                                # call function for substitution rule
                                inventory_item[item_var_key] = sub_fn(**_locals)
                            else:
                                inventory_item[item_var_key] = item_var[item_var_key]

                    # check group_vars -- entries with the proper index will be added
                    group_vars = ans_setting.get('group_vars', []) or []
                    for group_var in group_vars:
                        # 'index' mandatory
                        index = group_var['index']
                        if index == i or index == 'all':
                            for group_var_key in group_var:
                                if group_var_key != 'index':
                                    inventory_item[group_var_key] = group_var[group_var_key]

                    inventory_line = inventory_host_name + _SPACES + _SPACES.join(
                        ("%s=%s" % (k, v) for (k, v) in inventory_item.items()))
                    inventory_group.append(inventory_line)

        inventory_file_content = inventory_template.render(template_vars)
        project_path = self.config['project_path']
        utils.save_string_to_file(inventory_file_content, os.path.join(project_path, 'ansible_inventory'))

    def substitute_ansible_host(self, **kwargs):
        _locals = kwargs
        ans_host_val = _locals['item_var']['ansible_host']
        nodes = _locals['cloud_nodes']
        host_name = _locals['host_name']
        node = next(node for node in nodes if node.name == host_name)

        if ans_host_val == 'private_ip':
            if len(node.private_ips) > 0:
                ip = node.private_ips[0]
            elif len(node.public_ips) > 0:
                ip = node.public_ips[0]
                self.logger.warn(
                    "'ansible_host' for host '%s' was substituted with a "
                    "public ip instead of a private one. No private ips present.",
                    host_name)
            else:
                self.logger.error(
                    "Can't substitute 'ansible_host' for host '%s' because "
                    "it doesn't have any private nor public ips associated. Skipping...",
                    host_name)
                return ans_host_val
        else:
            if len(node.public_ips) > 0:
                ip = node.public_ips[0]
            elif len(node.private_ips) > 0:
                ip = node.private_ips[0]
                self.logger.warn(
                    "'ansible_host' for host '%s' was substituted with a "
                    "private ip instead of a public one. No public ips present.",
                    host_name)
            else:
                self.logger.error(
                    "Can't substitute 'ansible_host' for host '%s' because "
                    "it doesn't have any private nor public ips associated. Skipping...",
                    host_name)
                return ans_host_val

        self.logger.debug("Substituting %s host's item_var.ansible_host value from '%s' to '%s'", host_name, ans_host_val, ip)
        return ip

    def substitute_host_name(self, **kwargs):
        _locals = kwargs
        host_name = _locals['inventory_host_name']
        self.logger.debug("Substituting 'hostname' to '%s'", host_name)
        return host_name