## TODO pull containers, create singularity/apptainer from dockerhub github registry, local registry
from dataclasses import dataclass
from functools import cached_property

# container class
@dataclass
class Container:
    pass


@dataclass
class DockerContainer(Container):
    pass


@dataclass
class SingularityContainer(Container):
    pass


# This is where you get the containters from
class Registry:
    def __init__(self):
        pass

    def get_docker(self):
        pass

    def get_singularity(self):
        pass

    @cached_property
    def containers(self):
        pass

    def __str__(self):
        pass

    def __repr__(self):
        pass

