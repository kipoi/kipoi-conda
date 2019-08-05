"""Conda helper files

Reusing code from: https://github.com/conda/conda-api/blob/master/conda_api.py
"""
from __future__ import absolute_import
from __future__ import print_function

import os
import json
import sys
import subprocess
from subprocess import Popen, PIPE, STDOUT, check_output
from collections import OrderedDict
from kipoi_utils import yaml_ordered_dump, unique_list
from kipoi_utils.utils import _call_command
import six
import logging

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())





class CondaError(Exception):
    "General Conda error"
    pass


def create_env(env_name, conda_deps, dry_run=False):
    """Create new environment given parsed dependencies

    Args:
      conda_dependencies: OrderedDict of the `dependencies` field in Conda's environment.yaml.
        `model.dependencies.conda` field in Model or Dataloader.
      env_name: Environment name
    """
    # check if the environment already exists
    if env_exists(env_name):
        logger.info("Conda environment: {0} already exists. Skipping the installation.".
                    format(env_name))
        return None

    # write the env to file
    env_dict = OrderedDict([
        ("name", env_name),
        ("dependencies", conda_deps)
    ])
    tmp_dir = "/tmp/kipoi"
    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir)
    tmp_file_path = "{tmp_dir}/{env_name}.yml".format(tmp_dir=tmp_dir,
                                                      env_name=env_name)
    with open(tmp_file_path, 'w') as f:
        f.write(yaml_ordered_dump(env_dict, indent=4, default_flow_style=False))

    # create the environment
    return create_env_from_file(tmp_file_path, dry_run=dry_run)



def get_env_path(env_name):
    for env in get_envs():
        if os.path.basename(env) == env_name:
            return env
    return None


def call_script_in_env(filename, env_name=None, use_current_python=False, args=None, cwd=None): 
    """run an python script in a certain conda enviroment in a background
    process.
    
    Args:
        filename (str): path to the python script
        env_name (str or None, optional): Name of the conda enviroment.
        use_current_python (bool, False) If true, the current python executable will be used
        (this is useful for testing purposes )
        args (None, optional): args to pass to the script
    
    Returns:
        Popen: instance of Popen / running program
    """


    def activate_env(env_name=None,env_path=None):
        if env_path is None:
            assert env_name is not None
            env_path = get_env_path(env_name)
        bin_path = os.path.join(env_path,'bin')
        new_env = os.environ.copy()
        new_env['PATH'] = bin_path + os.pathsep + new_env['PATH']

    if use_current_python:
        python_path = sys.executable
    else:
        env_path = get_env_path(env_name=env_name)
        activate_env(env_path=env_path)
        python_path = os.path.join(env_path,'bin','python')

    #subprocess.run(, shell=True)
    # The os.setsid() is passed in the argument preexec_fn so
    # it's run after the fork() and before  exec() to run the shell.
    if args is None:
        args = []
    
    pro = subprocess.Popen([python_path, filename] + list(args), stdout=subprocess.PIPE, 
                           shell=False, close_fds=True,  preexec_fn=os.setsid,cwd=cwd)
    return pro



def get_kipoi_bin(env_name):
    """Returns the path to the kipoi executable in {env_name} environment
    """
    env_root = get_env_path(env_name)
    if env_root is None:
        raise ValueError("Conda environment {0} doesn't exist".format(env_name))
    out_path = os.path.join(env_root, "bin", "kipoi")
    if not os.path.exists(out_path):
        raise ValueError("kipoi is not installed in conda environment: {0}".format(env_name))
    return out_path


def create_env_from_file(env_file, use_stdout=False, dry_run=False):
    cmd_list = ["env", "create", "--file", env_file]
    return _call_conda(cmd_list, use_stdout=use_stdout, dry_run=dry_run)


def get_conda_version():
    # ret_code, stdout = _call_conda(["--version"], use_stdout=True, return_logs_with_stdout = True)
    p = Popen(["conda", "--version"], stdout=PIPE, stderr=PIPE, universal_newlines=True)
    # Poll process for new output until finished
    sout = []
    serr = []
    for stdout_line in iter(p.stdout.readline, ""):
        sout.append(stdout_line.rstrip())
    p.stdout.close()
    for stderr_line in iter(p.stderr.readline, ""):
        serr.append(stderr_line.rstrip())
    p.stderr.close()
    return_code = p.wait()
    out = sout
    if len(sout) == 0:
        out = serr

    if return_code != 0 or len(out) != 1:
        raise Exception("Could not retrieve conda version. Please check conda installation.")
    return out[0]


def install_conda(conda_deps, channels=["defaults"], dry_run=False):
    """Install conda packages

    Args:
      conda_deps: list of conda packages to be installed
      channels: list of conda channels to use
    """
    conda_deps_wo_python = [x for x in conda_deps if "python" != x[:6]]
    if conda_deps_wo_python:
        cmd_list = ["install", "-y"]
        if channels:
            cmd_list += ["--channel={0}".format(c) for c in channels] + ["--override-channels"]
            # `--override-channels` is here in order to increase reproducibility
            # on different computers with different ~/.condarc file
        cmd_list += conda_deps_wo_python
        return _call_conda(cmd_list, use_stdout=True, dry_run=dry_run)


def install_pip(pip_deps, dry_run=False):
    if pip_deps:
        cmd_list = ["install"] + list(pip_deps)
        return _call_pip(cmd_list, use_stdout=True, dry_run=dry_run)


def remove_env(env_name, dry_run=False):
    cmd_list = ["env", "remove", "-y", "-n", env_name]
    return _call_conda(cmd_list, use_stdout=True, dry_run=dry_run)


def get_envs():
    """
    Return all of the (named) environment (this does not include the root
    environment), as a list of absolute path to their prefixes.
    """
    json_str = check_output(["conda", "info", "--json"]).decode()
    info = json.loads(json_str)
    return info['envs']


def env_exists(env):
    return env in [os.path.basename(x) for x in get_envs()]


def _call_conda(extra_args, use_stdout=False, return_logs_with_stdout=False, dry_run=False):
    return _call_command("conda", extra_args, use_stdout, return_logs_with_stdout, dry_run=dry_run)


def _call_pip(extra_args, use_stdout=False, dry_run=False):
    return _call_command("pip", extra_args, use_stdout, dry_run=dry_run)


def _call_and_parse(extra_args, dry_run=False):
    stdout, stderr = _call_conda(extra_args, dry_run=dry_run)

    if stderr.strip():
        raise Exception('conda %r:\nSTDERR:\n%s\nEND' % (extra_args,
                                                         stderr.decode()))
    return json.loads(stdout.decode())


def parse_conda_package(dep):
    """Parse conda package into channel and environment

    Args:
      dep: string in the form '<channel>::<package>' or '<package>'

    Returns:
      tuple: ('<channel>', '<package>') or ('defaults', '<package>')
    """
    if "::" in dep:
        try:
            channel, package = dep.split("::")
        except ValueError:
            raise ValueError("The conda dependency: {0} couldn't be properly parsed. ".format(dep) +
                             "Use the following syntax: <channel>::<package> or <package>")
        return (channel, package)
    else:
        return ("defaults", dep)


def version_split(s, delimiters={"=", ">", "<", "~"}):
    """Split the string by the version:
    mypacakge<=2.4,==2.4 -> (mypacakge, <=2.4,==2.4)

    In [40]: version_split("asdsda>=2.4,==2")
    Out[40]: ('asdsda', ['>=2.4', '==2'])

    In [41]: version_split("asdsda>=2.4")
    Out[41]: ('asdsda', ['>=2.4'])

    In [42]: version_split("asdsda")
    Out[42]: ('asdsda', [])
    """
    for i, c in enumerate(s):
        if c in delimiters:
            return (s[:i], s[i:].split(","))
    return (s, [])


def normalize_pip(pip_list):
    """Normalize a list of pip dependencies

    Args:
      pip_list: list of pip dependencies

    Returns:
      normalized pip
    """

    d_list = OrderedDict()
    for d in pip_list:
        package, versions = version_split(d)
        if package in d_list:
            d_list[package] = unique_list(d_list[package] + versions)
        else:
            d_list[package] = versions
    return [package + ",".join(versions) for package, versions in six.iteritems(d_list)]


def get_package_version(package):
    """Get installed package version

    # Arguments
      package: package name. Example: `kipoi`

    # Returns
      (str) if the package is installed and None otherwise
    """
    import pkg_resources
    try:
        return pkg_resources.get_distribution(package).version
    except pkg_resources.DistributionNotFound:
        return None


def compatible_versions(installed_version, req_version):
    from pkg_resources import parse_version
    installed_version = parse_version(installed_version)
    if req_version.startswith(">="):
        return installed_version >= parse_version(req_version[2:])
    elif req_version.startswith("<="):
        return installed_version <= parse_version(req_version[2:])
    elif req_version.startswith("=="):
        return installed_version == parse_version(req_version[2:])
    elif req_version.startswith("<"):
        return installed_version < parse_version(req_version[1:])
    elif req_version.startswith(">"):
        return installed_version > parse_version(req_version[1:])
    else:
        raise ValueError("Package prefix {} needs to be from >=,<=, ==, >, <".
                         format(req_version))


def is_installed(package):
    """Test if the package is installed

    # Arguments
      package: package string, can also contain version: mypacakge<=2.4,==2.4
    """
    package, required_versions = version_split(package)
    installed_version = get_package_version(package)
    if installed_version is None:
        # package is for sure not installed
        return False
    else:
        for req_version in required_versions:
            return compatible_versions(installed_version, req_version)
        return True
