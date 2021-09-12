import os


def get_variable(name, default):

    env_default = os.environ.get("BLOCKCHAIN_{}".format(name.upper()), default)
    return env_default
