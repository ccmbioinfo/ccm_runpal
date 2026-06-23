import os
import subprocess
from pathlib import Path
import shlex
from typing import Dict
import tempfile

from runpal.utils import *

class ContainerRunner:
    """
    A class to run containers with various configuration options.

    Supports Singularity/Apptainer and Docker engines, with optional SLURM submission.
    """

    def __init__(self, engine: str, container_path: str, module_version: Optional[str] = None) -> None:
        """
        Initialize the container runner.

        :param engine: Container engine ("singularity", "apptainer", or "docker").
        :type engine: str
        :param container_path: Path to `.sif` for singularity/apptainer, or Docker image name for docker.
        :type container_path: str
        :param module_version: Optional module version suffix for SLURM module load.
        :type module_version: str | None
        :return: None
        :rtype: None
        :raises ContainerError: If engine is invalid, container path is invalid, or docker image is not available.
        """
        engine = engine.strip().lower()
        if engine not in {"singularity", "docker", "apptainer"}:
            raise ContainerError(f"Unsupported engine: {engine}")

        self.engine = engine
        self.module_version = module_version
        self.bind_mounts = []
        self.use_gpu = False

        if engine in {"singularity", "apptainer"}:
            if not Path(container_path).exists():
                raise ContainerError(f"{container_path} does not exist")
            if Path(container_path).suffix != ".sif":
                raise ContainerError("Singularity/Apptainer requires a .sif file")
            self.container_path = container_path
        else:
            self.image_name = container_path
            if not self._docker_image_exists(self.image_name):
                raise ContainerError(f"Docker image does not exist locally: {self.image_name}.")



    def _docker_image_exists(self, image_name: str) -> bool:
        """
        Check whether a Docker image exists locally.

        :param image_name: Docker image name.
        :type image_name: str
        :return: True if image exists locally, otherwise False.
        :rtype: bool
        :raises ContainerError: If Docker CLI is not available.
        """
        try:
            result = subprocess.run(
                ["docker", "image", "inspect", image_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            return result.returncode == 0
        except FileNotFoundError as e:
            raise ContainerError("Docker CLI is not available on PATH.") from e

    def enable_gpu(self) -> None:
        """
        Enable GPU support for container execution.

        :return: None
        :rtype: None
        """
        self.use_gpu = True

    def add_bind_mount(self, host_mount: str, container_mount: str) -> None:
        """
        Add a bind mount mapping.

        :param host_mount: Host path to mount.
        :type host_mount: str
        :param container_mount: Destination path inside container.
        :type container_mount: str
        :return: None
        :rtype: None
        :raises ContainerError: If host path does not exist.
        """
        if not Path(host_mount).exists():
            raise ContainerError(f"Host path does not exist: {host_mount}")
        self.bind_mounts.append({"host": host_mount, "container": container_mount})

    def _build_container_command(self, command_list: list[str]) -> list[str]:
        """
        Dispatch command building to engine-specific builder.

        :param command_list: Command tokens to run inside container.
        :type command_list: list[str]
        :return: Full container command tokens.
        :rtype: list[str]
        """
        if self.engine in {"singularity", "apptainer"}:
            return self._build_singularity_command(command_list)
        return self._build_docker_command(command_list)

    def _build_docker_command(self, command_list: list[str]) -> list[str]:
        """
        Build Docker execution command.

        :param command_list: Command tokens to run inside container.
        :type command_list: list[str]
        :return: Docker command tokens.
        :rtype: list[str]
        """
        cmd = ["docker", "run"]
        for bind in self.bind_mounts:
            cmd.append(f"--volume={bind['host']}:{bind['container']}")
        if self.use_gpu:
            cmd += ["--gpus", "all"]
        cmd.append(self.image_name)
        cmd.extend(command_list)

        return cmd

    def _module_load_line(self) -> str:
        """
        Build module load line for Singularity/Apptainer.

        :return: Module load command.
        :rtype: str
        """
        if self.engine == "singularity":
            module_name = "Singularity"
        else:
            module_name = "Apptainer"

        if self.module_version:
            return f"module load {module_name}/{self.module_version}"
        return f"module load {module_name}"

    def _build_singularity_command(self, command_list: list[str]) -> list[str]:
        """
        Build Singularity/Apptainer execution command.

        :param command_list: Command tokens to run inside container.
        :type command_list: list[str]
        :return: Singularity/Apptainer command tokens.
        :rtype: list[str]
        """
        if self.engine == "singularity":
            cmd = ["singularity", "exec"]
        else:
            cmd = ["apptainer", "exec"]
        if self.use_gpu:
            cmd.append("--nv")
        for bind in self.bind_mounts:
            cmd.append(f"--bind={bind['host']}:{bind['container']}")
        cmd.append(self.container_path)
        cmd.extend(command_list)
        return cmd

    def run(self, command: str | list[str], **subprocess_kwargs) -> subprocess.CompletedProcess:
        """
        Run a command in the configured container.

        :param command: Command string or token list.
        :type command: str | list[str]
        :param subprocess_kwargs: Extra keyword args forwarded to ``subprocess.run``.
        :type subprocess_kwargs: dict
        :return: Completed subprocess result.
        :rtype: subprocess.CompletedProcess
        :raises ContainerSubprocessError: If command exits non-zero.
        :raises ContainerError: If subprocess invocation fails.
        """
        if isinstance(command, str):
            command_list = shlex.split(command)
        else:
            command_list = command
        cmd = self._build_container_command(command_list)
        try:
            result = subprocess.run(cmd, **subprocess_kwargs, capture_output=True, text=True)
            if result.returncode != 0:
                raise ContainerSubprocessError(result.returncode, result.stderr)
            return result
        except subprocess.SubprocessError as e:
            raise ContainerError(f"Subprocess error: {e}")

    def run_slurm(self, command: str | list[str], **slurm_kwargs) -> str:
        """
        Submit a container command as a SLURM batch job.

        :param command: Command string or token list.
        :type command: str | list[str]
        :param slurm_kwargs: SLURM parameters validated by ``SlurmParams``.
        :type slurm_kwargs: dict
        :return: Submitted SLURM job ID.
        :rtype: str
        :raises ContainerError: If engine is docker.
        :raises ContainerSlurmError: If validation fails or submission fails.
        """
        if self.engine == "docker":
            raise ContainerError("SLURM is not supported for Docker")
        params = SlurmParams(**slurm_kwargs)
        if isinstance(command, str):
            command_list = shlex.split(command)
        else:
            command_list = command
        container_cmd = " ".join(self._build_container_command(command_list))

        if params.preset == "small":
            params.ntasks = 1
            params.cpus_per_task = 2
            params.mem = "10G"
        elif params.preset == "regular":
            params.ntasks = 1
            params.cpus_per_task = 4
            params.mem = "60G"
        elif params.preset == "large":
            params.ntasks = 1
            params.cpus_per_task = 10
            params.mem = "110G"

        lines = ["#!/bin/bash"]

        lines.append(f"#SBATCH --job-name={params.job_name}")
        lines.append(f"#SBATCH --time={params.time}")
        lines.append(f"#SBATCH --mem={params.mem}")
        lines.append(f"#SBATCH --output={params.output}")
        lines.append(f"#SBATCH --error={params.error}")
        lines.append(f"#SBATCH --ntasks={params.ntasks}")
        lines.append(f"#SBATCH --nodes={params.nodes}")
        if params.partition:
            lines.append(f"#SBATCH --partition={params.partition}")
        if params.reservation:
            lines.append(f"#SBATCH --reservation={params.reservation}")

        if params.cpus_per_task:
            lines.append(f"#SBATCH --cpus-per-task={params.cpus_per_task}")

        if params.gpu_type:
            if params.gpu_type not in self.GPU_MAP:
                raise ContainerSlurmError(f"Unsupported gpu_type: {params.gpu_type}")
            gpu_name = self.GPU_MAP[params.gpu_type]
            gpu_num = params.gpus if params.gpus is not None else 1
            lines.append(f"#SBATCH --gres=gpu:{gpu_name}:{gpu_num}")
        elif self.use_gpu:
            gpu_num = params.gpus if params.gpus is not None else 1
            lines.append(f"#SBATCH --gpus {gpu_num}")
        elif params.gpus is not None:
            raise ContainerSlurmError("GPU flag is not set but gpus parameter was provided.")

        if params.additional_sbatch:
            for key, value in params.additional_sbatch.items():
                lines.append(f"#SBATCH --{key}={value}")

        lines.append("")
        lines.append(self._module_load_line())
        lines.append(container_cmd)

        script = "\n".join(lines)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            f.write(script)
            script_path = f.name

        try:
            result = subprocess.run(
                ["sbatch", script_path],
                capture_output=True,
                text=True,
                check=True
            )
            job_id = result.stdout.strip().split()[-1]
            return job_id
        except subprocess.CalledProcessError as e:
            raise ContainerSlurmError(
                f"SLURM submission failed (code {e.returncode}): {(e.stderr or '').strip()}"
            )
        except subprocess.SubprocessError as e:
            raise ContainerSlurmError(f"SLURM submission failed: {e}")
        finally:
            os.unlink(script_path)

    def check_slurm_job_status(self, job_id: str) -> str:
        """
        Check SLURM job status.

        :param job_id: SLURM job ID.
        :type job_id: str
        :return: Job status code/state.
        :rtype: str
        :raises ContainerSlurmError: If status lookup fails.
        """
        try:
            result = subprocess.run(
                ["squeue", "-j", job_id, "-h", "-o", "%t"],
                capture_output=True,
                text=True,
                check=True
            )
            status = result.stdout.strip()
            if not status:
                # Check if job is completed or failed
                result = subprocess.run(
                    ["sacct", "-j", job_id, "--format=State", "-P", "-n"],
                    capture_output=True,
                    text=True
                )
                status_lines = result.stdout.strip().split('\n')
                if status_lines and status_lines[0]:
                    return status_lines[0]
                return "COMPLETED"  # Assume completed if not found
            return status
        except subprocess.SubprocessError as e:
            raise ContainerSlurmError(f"Failed to check SLURM job status: {str(e)}")

    def get_slurm_job_info(self, job_id: str) -> Dict[str, str]:
        """
        Fetch detailed SLURM job information.

        :param job_id: SLURM job ID.
        :type job_id: str
        :return: Parsed job information map.
        :rtype: dict[str, str]
        :raises ContainerSlurmError: If job info lookup fails.
        """
        try:
            result = subprocess.run(
                ["scontrol", "show", "job", job_id],
                capture_output=True,
                text=True,
                check=True
            )
            job_info = {}
            for line in result.stdout.split('\n'):
                for item in line.strip().split():
                    if '=' in item:
                        key, value = item.split('=', 1)
                        job_info[key] = value
            return job_info
        except subprocess.SubprocessError as e:
            raise ContainerSlurmError(f"Failed to get SLURM job info: {str(e)}")