from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import docker
import subprocess

# set up the client, this is up to you before you use the docker clinent
#docker_client = docker.from_env()


@dataclass
class Docker:
    name: str
    client: docker.DockerClient

    @classmethod
    def from_file(cls, client, dockerfile: str | Path, tag: str, ) -> "Docker":
        """
        build a docker container from file
        :param client: docker client
        :param dockerfile: docker file path
        :param tag: tags for the container
        :return: returns a docker class and a local docker image
        """
        dockerfile = Path(dockerfile)
        client.images.build(path=str(dockerfile.parent), dockerfile=dockerfile.name, tag=tag, )
        return cls(tag)

    @classmethod
    def pull(cls, client, image: str) -> "Docker":
        """
        pull a docker image from a docker registry, this can be a local one or dockerhub that depends on what your client is
        :param client: docker client
        :param image: which docker image to pull
        :return: a docker image instance
        """
        client.images.pull(image)
        return cls(image)

    def push(self, client):
        """
        push an image to a docker registry, this can be a local one or dockerhub that depends on what your client is
        :param client: docker client
        :return: None, pushes the client to hub
        """
        client.images.push(self.name)


@dataclass
class Singularity:
    path: Path

    @classmethod
    def from_file(cls, definition_file: str | Path, output: str | Path) -> "Singularity":
        """
        build a singularity container from file
        :param definition_file: path for the def file
        :param output: path to the .sif file to be created
        :return: the path if successfully created
        """
        output = Path(output)
        subprocess.run(["apptainer", "build", str(output), str(definition_file), ], check=True,)
        return cls(output)

    @classmethod
    def from_docker(cls,  docker_image: Docker | str, output: str | Path,) -> "Singularity":
        """
        build a singularity container from docker, the container must be available locally
        :param docker_image: name of the image or an instance of Docker
        :param output: where to create the sif file
        :return: the path of the sif file if successfully created
        """
        image = (docker_image.name if isinstance(docker_image, Docker) else docker_image)
        output = Path(output)
        subprocess.run(["apptainer", "build", str(output), f"docker-daemon://{image}",], check=True,)
        return cls(output)

    @classmethod
    def from_dockerfile(cls, dockerfile: str | Path, output: str | Path, temp_tag: str,) -> "Singularity":
        """
        Create a singularity container from dockerfile, this first creates the docker image and then the singularith container
        :param dockerfile: path to the dockerfile
        :param output: where to create the sif file
        :param temp_tag: tag for the container because the image will be created locally
        :return: the path of the sif file if successfully created
        """
        docker_img = Docker.from_file(dockerfile=dockerfile, tag=temp_tag,)

        return cls.from_docker(docker_img,output,)

    @classmethod
    def pull(cls, uri: str,  output: str | Path ) -> "Singularity":
        """
        pull a singularity container from uri
        :param uri: uri to pull, may be from singulaity hub
        :param output: path for the sif file
        :return: path for the sif file if successfully created
        """
        output = Path(output)

        subprocess.run(["apptainer", "pull", str(output), uri,],
            check=True,
        )

        return cls(output)

    def push(self, remote_uri: str):
        """
        push the container to the remote uri
        :param remote_uri: remote uri to push
        :return: none unless there is an error
        """
        subprocess.run(["apptainer", "push",  str(self.path),   remote_uri, ], check=True,)