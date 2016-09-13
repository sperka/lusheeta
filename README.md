# cpswtng-cloud-cli

This set of scripts helps you to manage separate clusters in your cloud. The tool lets you `create` and `cleanup` a
cluster of your choice (see #Configuration).

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
    
 * `network` - the network settings for your cluster (when creating)
    * `cidr` - the CIDR for your cluster's network. 
        * default: `auto`
        * possible values: `auto` or `XXX.XXX.XXX.0/24`
    * `cidr_template` - the CIDR template. Currently the script will substitute the `X` character from the template. 
        * default: `10.X.100.0/24`
        * __Required__ when `cidr == auto`, otherwise _optional_ 
    * `ext_net_name` - the name of the gateway for your network to connect to the external network
        * default: `ext-net`
        
        
        
        
---

** For OpenStack networking the
[official OpenStack SDK](http://developer.openstack.org/sdks/python/openstacksdk/users/index.html) was used as libcloud
doesn't support the required functionalities (i.e. networking).