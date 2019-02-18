import logging
import related

from . import utils as conda_utils
from kipoi_utils.external.related.fields import StrSequenceField, NestedMappingField, TupleIntField, AnyField, UNSPECIFIED
from kipoi_utils.external.related.mixins import RelatedConfigMixin, RelatedLoadSaveMixin
from kipoi_utils import unique_list

from collections import OrderedDict

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

@related.mutable(strict=False)
class Dependencies(RelatedConfigMixin):
    conda = StrSequenceField(str, default=[], required=False, repr=True)
    pip = StrSequenceField(str, default=[], required=False, repr=True)
    # not really required
    conda_channels = related.SequenceField(str, default=["defaults"],
                                           required=False, repr=True)

    def __attrs_post_init__(self):
        """
        In case conda or pip are filenames pointing to existing files,
        read the files and populate the package names
        """
        if len(self.conda) == 1 and self.conda[0].endswith(".txt") and \
           os.path.exists(self.conda[0]):
            # found a conda txt file
            object.__setattr__(self, "conda", read_txt(self.conda[0]))

        if len(self.pip) == 1 and self.pip[0].endswith(".txt") and \
           os.path.exists(self.pip[0]):
            # found a pip txt file
            object.__setattr__(self, "pip", read_txt(self.pip[0]))

    def all_installed(self, verbose=False):
        """Validate if all the dependencies are installed as requested

        Args:
          verbose: if True, display warnings if the dependencies are not installed

        Returns:
          (bool): True if all the required package versions are installed
            and False otherwise
        """
        norm = self.normalized()
        for pkg in list(norm.conda) + list(norm.pip):
            if not conda_utils.is_installed(pkg):
                if verbose:
                    pkg_name, req_version = conda_utils.version_split(pkg)
                    found_version = conda_utils.get_package_version(pkg_name)
                    if found_version is None:
                        print("Package '{}' is not installed".
                              format(pkg_name))
                    else:
                        print("Installed package '{}={}' doesn't "
                              "comply with '{}'".
                              format(pkg_name, found_version, pkg))
                return False
        return True

    def install_pip(self, dry_run=False):
        print("pip dependencies to be installed:")
        print(self.pip)
        if dry_run:
            return
        else:
            conda_utils.install_pip(self.pip)

    def install_conda(self, dry_run=False):
        print("Conda dependencies to be installed:")
        print(self.conda)
        if dry_run:
            return
        else:
            channels, packages = self._get_channels_packages()
            conda_utils.install_conda(packages, channels)

    def install(self, dry_run=False):
        self.install_conda(dry_run)
        self.install_pip(dry_run)

    def merge(self, dependencies):
        """Merge one dependencies with another one

        Use case: merging the dependencies of model and dataloader

        Args:
            dependencies: Dependencies instance

        Returns:
            new Dependencies instance
        """
        return Dependencies(
            conda=unique_list(list(self.conda) + list(dependencies.conda)),
            pip=conda_utils.normalize_pip(list(self.pip) + list(dependencies.pip)),
            conda_channels=unique_list(list(self.conda_channels) + list(dependencies.conda_channels))
        )

    def normalized(self):
        """Normalize the list of dependencies
        """
        channels, packages = self._get_channels_packages()
        if isinstance(packages, related.types.TypedSequence):
            packages = packages.list
        if isinstance(channels, related.types.TypedSequence):
            channels = channels.list

        return Dependencies(
            conda=packages,
            pip=conda_utils.normalize_pip(list(self.pip)),
            conda_channels=channels)

    def _get_channels_packages(self):
        """Get conda channels and packages separated from each other(by '::')
        """
        if len(self.conda) == 0:
            return self.conda_channels, self.conda
        channels, packages = list(zip(*map(conda_utils.parse_conda_package, self.conda)))
        channels = unique_list(list(channels) + list(self.conda_channels))
        packages = unique_list(list(packages))

        # Handle channel order
        if "bioconda" in channels and "conda-forge" not in channels:
            # Insert 'conda-forge' right after bioconda if it is not included
            channels.insert(channels.index("bioconda") + 1, "conda-forge")
        if "pysam" in packages and "bioconda" in channels:
            if channels.index("defaults") < channels.index("bioconda"):
                logger.warning("Swapping channel order - putting defaults last. " +
                            "Using pysam bioconda instead of anaconda")
                channels.remove("defaults")
                channels.insert(len(channels), "defaults")
        return channels, packages

    def to_env_dict(self, env_name):
        deps = self.normalized()
        channels, packages = deps._get_channels_packages()
        if isinstance(packages, related.types.TypedSequence):
            packages = packages.list
        if isinstance(channels, related.types.TypedSequence):
            channels = channels.list

        env_dict = OrderedDict(
            name=env_name,
            channels=channels,
            dependencies=packages + [OrderedDict(pip=conda_utils.normalize_pip(deps.pip))]
        )
        return env_dict

    @classmethod
    def from_env_dict(self, dict):
        cfg = {}
        cfg["conda_channels"] = dict['channels']
        cfg["conda"] = [el for el in dict['dependencies'] if not isinstance(el, OrderedDict)]
        pip = [el for el in dict['dependencies'] if isinstance(el, OrderedDict)]
        if len(pip) == 1:
            cfg["pip"] = pip[0]['pip']
        elif len(pip) > 1:
            raise Exception("Malformatted conda environment yaml!")
        return self.from_config(cfg)

    def to_env_file(self, env_name, path):
        """Dump the dependencies to a file
        """
        with open(path, 'w') as f:
            d = self.to_env_dict(env_name)

            # add python if not present
            add_py = True
            for dep in d['dependencies']:
                if isinstance(dep, str) and dep.startswith("python"):
                    add_py = False

            if add_py:
                d['dependencies'] = ["python"] + d['dependencies']
            # -----
            # remove fields that are empty
            out = []
            for k in d:
                if not (isinstance(d[k], list) and len(d[k]) == 0):
                    out.append((k, d[k]))
            # -----

            f.write(yaml_ordered_dump(OrderedDict(out),
                                      indent=2,
                                      default_flow_style=False))

    def gpu(self):
        """Get the gpu - version of the dependencies
        """
        def replace_gpu(dep):
            if dep.startswith("tensorflow") and "gpu" not in dep:
                new_dep = dep.replace("tensorflow", "tensorflow-gpu")
                logger.info("use gpu: Replacing the dependency {0} with {1}".format(dep, new_dep))
                return new_dep
            if dep.startswith("pytorch-cpu"):
                new_dep = dep.replace("pytorch-cpu", "pytorch")
                logger.info("use gpu: Replacing the dependency {0} with {1}".format(dep, new_dep))
                return new_dep
            return dep

        deps = self.normalized()
        return Dependencies(
            conda=[replace_gpu(dep) for dep in deps.conda],
            pip=[replace_gpu(dep) for dep in deps.pip],
            conda_channels=deps.conda_channels)

    def osx(self):
        """Get the os - x compatible dependencies
        """
        from sys import platform
        if platform != 'darwin':
            logger.warning("Calling osx dependency conversion on non-osx platform: {}".
                        format(platform))

        def replace_osx(dep):
            if dep.startswith("pytorch-cpu"):
                new_dep = dep.replace("pytorch-cpu", "pytorch")
                logger.info("osx: Replacing the dependency {0} with {1}".
                            format(dep, new_dep))
                return new_dep
            return dep

        deps = self.normalized()
        return Dependencies(
            conda=[replace_osx(dep) for dep in deps.conda],
            pip=[replace_osx(dep) for dep in deps.pip],
            conda_channels=deps.conda_channels)

    # @classmethod
    # def from_file(cls, path):
    #     """TODO instantiate Dependencies from a yaml file
    #     """
    #     pass