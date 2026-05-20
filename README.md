
<div style="text-align: center;">
    <img src="./assets/logo.png" width="900" alt="CCM RunPal logo" class="center">
</div>

<p align="center">
    <a href="" alt="Activity">
        <img src="https://img.shields.io/github/commit-activity/m/ccmbioinfo/runpal" /></a>
    <a href="" alt="stars">
        <img src="https://img.shields.io/github/stars/ccmbioinfo/runpal" /></a>
    <a href="" alt="Issues">
        <img src="https://img.shields.io/github/issues/ccmbioinfo/runpal" /></a>
    <a href="https://ccmbioinfo.github.io/runpal/">
        <img alt="Documentation" src="https://img.shields.io/website?url=https%3A%2F%2Fccmbioinfo.github.io%2Fccm_runpal%2F&label=Documentation"></a>
</p>

# CCM RunPal

A module for running Singularity/Apptainer or Docker containers with support for local and SLURM cluster execution.

## Overview

The `ContainerRunner` class provides a unified interface for:

- Running containers locally
- Submitting container jobs to SLURM
- Managing bind mounts and GPU access
- Monitoring SLURM job status

## Usage

### Basic Local Container Execution

```python
from benchmate.container_runner.container_runner import ContainerRunner

# Initialize with engine + container/image
runner = ContainerRunner(
    engine="singularity",  # or "apptainer" or "docker"
    container_path="/path/to/container.sif",  # for singularity/apptainer
    module_version="3.7.4"  # optional, for HPC module systems
)

# Add bind mounts (one host path per bind)
runner.add_bind_mount(
    host_mount="/host/path1",
    container_mount="/container/path1"
)

# Enable GPU support if needed
runner.enable_gpu()

# Run command in container
result = runner.run("echo hello", check=True)
print(result.stdout)
```

### Docker Local Execution

```python
runner = ContainerRunner(
    engine="docker",
    container_path="ubuntu:latest"  # image name (must exist locally)
)

# Add bind mounts (one host path per bind)
runner.add_bind_mount(
    host_mount="/host/path1",
    container_mount="/container/path1"
)

# Enable GPU support if needed
runner.enable_gpu()

result = runner.run("echo hello", check=True)
```

### SLURM Cluster Execution

```python
# Submit job to SLURM (Singularity/Apptainer only) with specific gpu short-hand and preset for mem and cpus
job_id = runner.run_slurm(
    command="python script.py",
    job_name="analysis_job",
    time="01:00:00",
    gpu_type="a100",  # optional GPU type
    preset="regular",  # optional: small | regular | large
    additional_sbatch={"partition": "special_features"}
)

# Submit job to SLURM (Singularity/Apptainer only) using any gpus
job_id = runner.run_slurm(
    command="python script.py",
    time="01:00:00",
    mem="16G",
    ntasks=1,
    cpus_per_task=4,
    gpus=1,
    additional_sbatch={"partition": "gen_gpu"}
)
```

### SLURM Presets

If `preset` is provided, it overrides `ntasks`, `cpus_per_task`, and `mem` with the following values:
- `small`
	- `ntasks=1`
	- `cpus_per_task=2`
	- `mem=10G`
- `regular`
	- `ntasks=1`
	- `cpus_per_task=4`
	- `mem=60G`
- `large`
	- `ntasks=1`
	- `cpus_per_task=10`
	- `mem=110G`

If both `preset` and manual CPU/memory parameters are provided, the preset values take precedence.

### SLURM Job Helpers

```python
status = runner.check_slurm_job_status(job_id)
job_info = runner.get_slurm_job_info(job_id)
```

## Key Features

### Container Execution

- Supports Singularity, Apptainer, and Docker
- Docker image existence is validated locally before execution
- Configurable bind mounts (one host path per bind)
- GPU support:
	- Singularity/Apptainer: `--nv`
	- Docker: `--gpus all`
- Commands executed via `subprocess.run`

### SLURM Integration

- Submits jobs via `sbatch`
- Supports resource presets: `small`, `regular`, `large`
- Supports GPU type mapping (`gpu_type`)
- Supports extra SBATCH parameters with `additional_sbatch`
- Automatically generates and cleans up temporary SBATCH scripts
- Job status/info helpers (`squeue`, `sacct`, `scontrol`)

### Error Handling

- Custom exception classes (`ContainerError`, `ContainerSubprocessError`, `ContainerSlurmError`)
- Subprocess error capturing
- SLURM job error handling

## Notes

- Singularity/Apptainer requires a `.sif` file path that exists.
- Docker requires a valid locally available image name (images are not auto-pulled).
- Bind mounts require valid host paths.
- SLURM submission requires access to a SLURM cluster and valid SBATCH parameters.
- SLURM execution is not supported for Docker.
- GPU support requires NVIDIA drivers and appropriate container configuration.
- GPU SLURM runs require `enable_gpu()`; if you pass `gpus` without enabling GPU, an error is raised.
- If `gpu_type` is provided, it must be one of the supported GPU types (`p100`, `v100`, `p40`, `l40`, `h100`, `h100_80`, `a100`).
- SLURM job submission may require additional configuration based on the cluster setup.