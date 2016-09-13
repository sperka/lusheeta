# cpswtng-cloud-cli

This set of scripts helps you to manage separate clusters in your cloud. The tool lets you `create` and `cleanup` a
cluster of your choice (see #Configuration).

---
# Usage

    $ ./main.py -h                                                                                                            2 ↵
    usage: main.py [-h] -a {create,cleanup,prepare_ansible,run_ansible}
                   [-c CONFIG] [-v]
                   project
    
    Cloud CLI tool
    
    positional arguments:
      project               the name of the project
    
    optional arguments:
      -h, --help            show this help message and exit
      -a | --action {create,cleanup,prepare_ansible,run_ansible}
                            the action to do
      -c | --config CONFIG
                            path to the configuration file
      -v, --verbose         set verbosity mode

---

# Configuration

You can find the configuration files in the `./config` dir.
 
## default.yml - main config

This configuration file is the main configuration for the CLI tool. You can set the following parameters:
 
 * `project`
    
    the name of the project (cluster) you want to manage.
    
 * `projects_dir` - the path to the default projects directory
    * default: `./projects`
   
 * `platform` - the cloud platform of your choice
    * default: `openstack`
    * currently supported platforms: `openstack`
    
 * `network` _dict_ - the network settings for your cluster (when creating)
    * `cidr` - the CIDR for your cluster's network. 
        * default: `auto`
        * possible values: `auto` or `XXX.XXX.XXX.0/24`
    * `cidr_template` - the CIDR template. Currently the script will substitute the `X` character from the template. 
        * default: `10.X.100.0/24`
        * __Required__ when `cidr == auto`, otherwise _optional_ 
    * `ext_net_name` - the name of the gateway for your network to connect to the external network
        * default: `ext-net`
        
 * `vm_management` _dict_ - vm management settings for your cluster (when creating)
    * `default_image_name` - the default name of the image to use to spin up a vm.
        If you don't specify the `image_name` property for a host, this value will be used.
        * default: `Ubuntu 14.04.2_20150505`
    * `default_vm_flavor` - the name of the flavor to spin up a vm.
        If you don't specify the `vm_flavor` property for a host, this value will be used.
        * default: `m1.medium`
    * `hosts_startup_timeout` - the amount of time (in seconds) to wait to spin up all the vms and then keep executing
        the rest of the script
        * default: `600`
    * `terminate_vm_poll` - the amount of time (in seconds) to wait between polls when terminating vms
        * default: `5`
        
 * `hosts` _array_ - the section to setup host configs. Each array item is a `host` _dict_, which is a configuration
                     for one host
    * `name` _required_ - the name of the host
    * `vm_flavor` _optional_ - the name of the flavor to spin up a vm. This property overrides `vm_management.default_vm_flavor`
    * `count` _optional_ - the number of vms to spin up with these properties. If this field is missing, default
                        value of `1` will be used.
    * `image_name` _optional_ - the name of the image to spin up a vm. This property overrides
        `vm_management.default_image_name`
    * `cloud_vars` _optional_ _array_ - implementation specific special variables. Each item in the array must be a
        _dict_ that contains the following parameter:
         * `index` _all | \<number\>_ - the index to which host to apply the current special var
            * possible values can be `all` or the index `<number>` of the host
            * see `config/default.yml` as example
            
            _Implemented options so far:_

            * `assignPublicIP` _boolean_ - when `true`, a public IP will be assigned to the `index`-th host
                
    * `ansible_settings` _array_ - the section to setup the ansible settings for the host. Each item in the array
                                    is a _dict_ with the following parameters:
        * `ansible_group` - which ansible group this host will belong to
        * `group_vars` _array_ - an array of _dict_ items to describe group-level variables. Each item must contain
                                an _index_ key and the desired parameter key with its value
          * `index` - which item in the list should have the parameter key
          * `parameter_key: parameter_value` - the parameter key-value to add in the inventory file for the current host
 
        * `item_vars` _array_ - an array of key-value pairs that _every_ item should contain in the group
                 
 * `ansible` _dict_ - ansible settings to setup the software infrastructure
    * `ansible_dir` - the path to directory where your ansible project files reside
    * `playbook` - relative path to the playbook to run your setup
    * `inventory_template` _optional_ - a _jinja2_ template file for your inventory to use
    * `ssh_config_template` _optional_ - a _jinja2_ template file for the `ssh.config` file
    * `ansible_cfg_template` _optional_ - a _jinja2_ template file for the `ansible.cfg` file
                 
                 
---

** For OpenStack networking the
[official OpenStack SDK](http://developer.openstack.org/sdks/python/openstacksdk/users/index.html) was used as libcloud
doesn't support the required functionalities (i.e. creating/removing subnets, networks, routers, etc).