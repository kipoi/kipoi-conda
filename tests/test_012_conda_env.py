"""Test conda env installation
"""
from collections import OrderedDict
import pytest
import tempfile
import kipoi_conda
from kipoi_conda import Dependencies
from kipoi_conda import (install_conda, call_script_in_env,install_pip, normalize_pip, parse_conda_package,
                         compatible_versions, is_installed, get_package_version, version_split)

import kipoi_utils
def fake_call_command(main_cmd, cmd_list, use_stdout=False, return_logs_with_stdout=False,dry_open=False, **kwargs):
    return main_cmd, cmd_list


def test_pip_merge():
    pip_list = ["package>=1.1,==1.4", "package2", "package2>=1.5",
                "package>=1.1,==1.4,==1.5", "package5"]
    assert normalize_pip(pip_list) == ['package>=1.1,==1.4,==1.5', 'package2>=1.5', 'package5']


def test_parse_conda_package():
    assert parse_conda_package("package") == ("defaults", "package")
    assert parse_conda_package("channel::package") == ("channel", "package")
    with pytest.raises(ValueError):
        parse_conda_package("channel::package::asds")


def test_Dependencies():
    dep = Dependencies(conda=["conda_pkg1", "conda_pkg2"],
                       pip=["pip_pkg1>=1.1", "pip_pkg2"])
    res = dep.to_env_dict("asd")
    assert res["name"] == "asd"
    assert res["channels"] == ["defaults"]
    assert res["dependencies"][0] == "conda_pkg1"
    assert res["dependencies"][1] == "conda_pkg2"
    assert res["dependencies"][2]["pip"][1] == "pip_pkg2"


def test_Dependencies_merge():
    dep1 = Dependencies(conda=["conda_pkg1", "conda_pkg2"],
                        pip=["pip_pkg1>=1.1", "pip_pkg2"])
    dep2 = Dependencies(conda=["conda_pkg1", "conda_pkg3>=1.1"],
                        pip=["pip_pkg1>=1.0", "pip_pkg2==3.3"])
    dep_merged = dep1.merge(dep2)
    assert dep_merged.conda == ['conda_pkg1',
                                'conda_pkg2',
                                'conda_pkg3>=1.1']
    assert dep_merged.pip == ['pip_pkg1>=1.1,>=1.0',
                              'pip_pkg2==3.3']

    assert dep_merged.conda_channels == ["defaults"]


def test_bioconda_channels():
    dep1 = Dependencies(conda=["conda_pkg1", "bioconda::conda_pkg2"],
                        pip=[])
    channels, packages = dep1._get_channels_packages()
    assert channels == ["defaults", "bioconda", "conda-forge"]
    dep1 = Dependencies(conda=["bioconda::conda_pkg2", "conda_pkg1"],
                        pip=[])
    channels, packages = dep1._get_channels_packages()
    assert channels == ["bioconda", "conda-forge", "defaults"]

    dep1 = Dependencies(conda=["bioconda::conda_pkg2"],
                        pip=[])
    channels, packages = dep1._get_channels_packages()
    assert channels == ["bioconda", "conda-forge", "defaults"]

    dep1 = Dependencies(conda=["conda-forge::conda_pkg2", "bioconda::conda_pkg2"],
                        pip=[])
    channels, packages = dep1._get_channels_packages()
    assert channels == ["conda-forge", "bioconda", "defaults"]

    dep1 = Dependencies(conda=["asd::conda_pkg2", "bioconda::conda_pkg2", "dsa::conda_pkg2"],
                        pip=[])
    channels, packages = dep1._get_channels_packages()
    assert channels == ["asd", "bioconda", "conda-forge", "dsa", "defaults"]


def test_handle_pysam():
    dep1 = Dependencies(conda=["conda_pkg1", "bioconda::pysam"],
                        pip=[])
    channels, packages = dep1._get_channels_packages()
    assert channels == ["bioconda", "conda-forge", "defaults"]

    dep1 = Dependencies(conda=["conda_pkg1", "bioconda::pybedtools"],
                        pip=[])
    channels, packages = dep1._get_channels_packages()
    assert channels == ["defaults", "bioconda", "conda-forge"]


def test_other_channels():
    dep1 = Dependencies(conda=["other::conda_pkg2", "conda_pkg1"],
                        pip=[])
    channels, packages = dep1._get_channels_packages()
    assert channels == ["other", "defaults"]
    dep1 = Dependencies(conda=["conda_pkg1", "other::conda_pkg2"],
                        pip=[])
    channels, packages = dep1._get_channels_packages()
    assert channels == ["defaults", "other"]


def test_create_env(monkeypatch):
    # import kipoi
    import kipoi_conda.utils
    from kipoi_conda.utils import create_env, env_exists, remove_env
    # monkeypatch.setattr(kipoi_conda.utils, '_call_and_parse', fake_call_command)
    dependencies = ["python=3.6", "numpy",
                    OrderedDict(pip=["tqdm"])
                    ]
    ENV_NAME = "kipoi-test-awerwerwerwer"

    assert not env_exists(ENV_NAME)

    def fake_env_exists(env_name):
        return False
    # monkeypatch.setattr(kipoi_conda.utils, 'env_exists', fake_env_exists)
    # monkeypatch.setattr(kipoi_utils.utils, '_call_command', fake_call_command)

    main_cmd, cmd_list = create_env(ENV_NAME, dependencies, dry_run=True)
    assert main_cmd == 'conda'
    assert cmd_list == ['env', 'create', '--file', '/tmp/kipoi/kipoi-test-awerwerwerwer.yml', '--experimental-solver=libmamba']

    # remove the environment
    main_cmd, cmd_list = remove_env(ENV_NAME, dry_run=True)
    assert main_cmd == 'conda'
    assert cmd_list == ['env', 'remove', '-y', '-n', 'kipoi-test-awerwerwerwer', '--experimental-solver=libmamba']

@pytest.mark.xfail
def test_create_env_wrong_dependencies():
    dependencies = ["python=3.6", "numpyxzy"]
    ENV_NAME = "kipoi-test-env2"
    if kipoi_conda.env_exists(ENV_NAME):
        kipoi_conda.remove_env(ENV_NAME)
    with pytest.raises(Exception):
        kipoi_conda.create_env(ENV_NAME, dependencies)


def test_install(monkeypatch):
    import kipoi_conda.utils
    conda_deps = ["python=3.6", "pep8"]
    pip_deps = ["tqdm"]

    # monkeypatch.setattr(kipoi_utils.utils, '_call_command', fake_call_command)

    main_cmd, cmd_list = install_conda(conda_deps, dry_run=True)
    assert main_cmd == 'conda'
    assert cmd_list == ['install', '-y', '--channel=defaults', '--override-channels', 'pep8', '--experimental-solver=libmamba']

    main_cmd, cmd_list = install_pip(pip_deps, dry_run=True)
    assert main_cmd == 'pip'
    assert cmd_list == ['install', 'tqdm']


def test_version_split():
    assert version_split("asdsda>=2.4,==2") == ('asdsda', ['>=2.4', '==2'])
    assert version_split("asdsda>=2.4") == ('asdsda', ['>=2.4'])
    assert version_split("asdsda>=2.4,~=2.3") == ('asdsda', ['>=2.4', '~=2.3'])
    assert version_split("asdsda~=2.4,>=2.3") == ('asdsda', ['~=2.4', '>=2.3'])
    assert version_split("asdsda~=2.4") == ('asdsda', ['~=2.4'])
    assert version_split("asdsda") == ('asdsda', [])


def test_compatible_versions():
    assert compatible_versions("1.10", '>=1.0')
    assert compatible_versions("1.10", '>1.0')
    assert not compatible_versions("1.10", '>=2.0')
    assert not compatible_versions("1.10", '>2.0')
    assert not compatible_versions("1.10", '==1.11')
    assert compatible_versions("1.10", '==1.10')
    assert compatible_versions("1.10", '<=1.10')
    assert not compatible_versions("1.10", '<=1.1')
    assert compatible_versions("1.10", '<=1.11')
    assert compatible_versions("1.10", '<1.11')
    with pytest.raises(ValueError):
        compatible_versions("1.10", '1<1.11')

    assert compatible_versions("0.10", '<1.11')


def test_package_version():
    import numpy as np
    import pandas as pd
    assert get_package_version("kipoi_conda") == kipoi_conda.__version__
    assert get_package_version("numpy") == np.__version__
    assert get_package_version("pandas") == pd.__version__
    assert get_package_version("package_doesnt_exist") is None


def test_is_installed():
    assert is_installed("kipoi_conda>=0.1")
    assert is_installed("kipoi_conda<=10.1")
    assert not is_installed("kipoi_conda>=10.1")
    assert is_installed("kipoi_conda>=0.1,>=0.2")
    assert is_installed("kipoi_conda>=0.1,>0.2")
    assert not is_installed("package_doesnt_exist")


def test_dependencies_all_installed():
    assert Dependencies(conda=["related"], pip=["kipoi_conda"]).all_installed()
    assert Dependencies(conda=["related"], pip=["kipoi_conda>=0.1"]).all_installed()
    assert Dependencies(conda=["related>0.1"], pip=["kipoi_conda>=0.1"]).all_installed()
    assert not Dependencies(conda=["related>0.1"], pip=["kipoi_conda>=10.1"]).all_installed()
    assert not Dependencies(conda=["related>0.1"], pip=["kipoi_conda>=10.1"]).all_installed(verbose=True)
    assert not Dependencies(conda=["package_doesnt_exist>0.1"], pip=["kipoi_conda>=10.1"]).all_installed(verbose=True)


script = R"""
import kipoi
if __name__ == "__main__":
    return 0
"""

def test_call_script_in_env():

    with  tempfile.NamedTemporaryFile(mode='w') as f:
        f.write(script)
        kipoi_conda.call_script_in_env(f.name, use_current_python=True)