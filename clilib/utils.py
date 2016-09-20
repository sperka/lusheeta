import os
import yaml

def load_yaml_config(cfg_file):
    with open(cfg_file, 'r') as cfg_file_stream:
        config_obj = yaml.load(cfg_file_stream)
    return config_obj


def write_yaml_config(cfg_file, content):
    with open(cfg_file, 'w') as cfg_file_stream:
        yaml.dump(content, cfg_file_stream)


supported_platforms = None


def load_supported_platforms_config():
    global supported_platforms
    if not supported_platforms:
        cfg_file = "config/supported_platforms.yml"
        supported_platforms = load_yaml_config(cfg_file)
    return supported_platforms


def import_platform_class(mod_name, class_name):
    mod = __import__("clilib." + mod_name)
    mod = getattr(mod, mod_name)
    mod = getattr(mod, class_name)
    return mod


def save_string_to_file(str, target_path, chmod=None):
    with open(target_path, "wb") as file_stream:
        file_stream.write(str)
    if chmod:
        os.chmod(target_path, chmod)


def static_vars(**kwargs):
    def decorate(func):
        for k in kwargs:
            setattr(func, k, kwargs[k])
        return func
    return decorate

