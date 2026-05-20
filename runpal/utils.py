from pydantic import BaseModel, ConfigDict

class TokenFetchError(Exception):
    """
    Exception used when a token could not be fetched.
    """
    pass

class ContainerError(Exception):
    """Base exception for Container-related errors."""
    pass

class ContainerSubprocessError(ContainerError):
    """Exception raised when an Container subprocess fails."""

    def __init__(self, returncode: int, stderr: str) -> None:
        """
        Initialize subprocess failure details.

        :param returncode: Subprocess return code.
        :type returncode: int
        :param stderr: Subprocess standard error output.
        :type stderr: str
        :return: None
        :rtype: None
        """
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(f"Container subprocess failed with return code {returncode}: {stderr}")

class ContainerSlurmError(ContainerError):
    """Exception raised for SLURM job-related errors."""
    pass

class SlurmParams(BaseModel):
    """
    Pydantic model for SLURM parameters used when submitting jobs.

    :param job_name: SLURM job name.
    :type job_name: str
    :param time: SLURM walltime (HH:MM:SS).
    :type time: str
    :param mem: Memory request (e.g., 4G, 60G).
    :type mem: str
    :param output: SLURM stdout filename pattern.
    :type output: str
    :param error: SLURM stderr filename pattern.
    :type error: str
    :param cpus_per_task: CPUs per task.
    :type cpus_per_task: int | None
    :param ntasks: Number of tasks.
    :type ntasks: int
    :param gpus: Number of GPUs.
    :type gpus: int | None
    :param nodes: Number of nodes.
    :type nodes: int
    :param preset: Resource preset (small, regular, large).
    :type preset: str | None
    :param gpu_type: GPU short name (p100, v100, p40, l40, h100, h100_80, a100).
    :type gpu_type: str | None
    :param partition: SLURM partition.
    :type partition: str | None
    :param reservation: SLURM reservation name.
    :type reservation: str | None
    :param additional_sbatch: Additional SBATCH directives.
    :type additional_sbatch: dict[str, str] | None
    """
    model_config = ConfigDict(extra='forbid')
    job_name: str = "Container_job"
    time: str = "01:00:00"
    mem: str = "4G"
    output: str = "slurm-%j.out"
    error: str = "slurm-%j.err"
    cpus_per_task: Optional[int] = None
    ntasks: int = 1
    gpus: Optional[int] = None
    nodes: int = 1
    preset: Optional[str] = None          # small, regular, large
    gpu_type: Optional[str] = None        # p100, v100, p40, l40, h100, h100_80, a100
    partition: Optional[str] = None
    reservation: Optional[str] = None
    additional_sbatch: Optional[Dict[str, str]] = None