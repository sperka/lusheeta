import logging
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

    def prepare_files(self):
        ansible_settings = self.config['ansible']
        inventory_template_path = ansible_settings.get('inventory_template')
        if inventory_template_path:
            self._generate_inventory_file()
        else:
            self.logger.warn("ansible.inventory_template not set. Skipping inventory file generation...")

    def _generate_inventory_file(self):
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
                    item_vars = ans_setting.get('item_vars')
                    if item_vars:
                        for item_var in item_vars:
                            for item_var_key in item_var:
                                inventory_item[item_var_key] = item_var[item_var_key]

                    # check group_vars -- entries with the proper index will be added
                    group_vars = ans_setting.get('group_vars')
                    if group_vars:
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

        x = inventory_template.render(template_vars)
        print x
