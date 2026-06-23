
<div style="text-align: center;">
    <img src="./assets/logo.png" width="900" alt="CCM RunPal logo" class="center">
</div>

<p align="center">
    <a href="" alt="Activity">
        <img src="https://img.shields.io/github/commit-activity/m/ccmbioinfo/ccm_runpal" /></a>
    <a href="" alt="stars">
        <img src="https://img.shields.io/github/stars/ccmbioinfo/ccm_runpal" /></a>
    <a href="" alt="Issues">
        <img src="https://img.shields.io/github/issues/ccmbioinfo/ccm_runpal" /></a>
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
from runpal.runner import ContainerRunner

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

There is a little bit of an overlap between the `SlurmRunner` (see below) and `ContainerRunner`, you can use whatever
one you like. Slurm runner is more for running general jobs, for example you have a database connection that you can pull data
from and that will automagically generate a slurm script and using slurm runner you can upload the script and submit the job in 
2 lines of code.

```python
from runpal.runner import ContainerRunner

c_runner=ContainerRunner()
status = c_runner.check_slurm_job_status(job_id)
job_info = c_runner.get_slurm_job_info(job_id)
```


## Logging in transfering files to and from HPC

This module is for general maintanence, accounting and other HPC related activities

```python
from runpal.slurm import SlurmRunner

runner=SlurmRunner(api_host="where.your.hpc.openapi.is", "slogin.your.hpc.com", "username", "password")

#create a jwt for slurm
token=runner.get_new_jwt() #by defaul this is good for a week, you can change the duration in second above, or just get a new one

#file operations
runner.send_file("where/your/file/is/locally", "where/you/want/the/file/tobe", force=False) #if true will overwrite otherwise will get an error
runner.create_directory("name_of_dir", "path_of_dir", exists_ok=True, follow_symlinks=True) #kind of self explanatory
runner.receive_file("remote_path_to_the_file", "where/to/downlaod/the/file", force=False)

#job operations
runner.run_job("command", "working_dir", options={})
runner.run_job_ssh("path to the script to run", "working_director", options={slurm job options})
```

The difference between `run_job` and `run_job_ssh` is the latter submits the job from a remote machine like your laptop, whereas the
other one submits the job from a login node. 

## Container Creation

This module allows you to create docker and singularit/apptainer containers from different sources. To be able to use
docker related features you need to create a docker client like so:

```python
import docker

client=docker.from_env() #assuming you have your credential in your env
```

`doccker.from_env` is just one way of creating a client. See [here](https://docker-py.readthedocs.io/en/stable/client.html) for more details.
Keep in mind that the client can be any kind of registry not just dockerhub. If you have one that you (or your work) has created
and maintains that's all good as well. 

After that you can create containers.

```python
import docker
from runpal.containers import Docker, Singularity

client = docker.from_env()

d_container=Docker(name="my_container")
d_container.from_file(client, "path to Dockerfile", tag="awesome:latest")
d_container.pull(client, "name of the image")
d_container.push(client) #uses the name and tag of self

#singlularity is as similar as it can be

s_container=Singularity(path="path to the sif file")
s_container.from_file(definition_file="def/file/path", output="where/to/save/the/file")
s_container.from_docker(docker_image="A Docker instances from above", output="file path")
s_container.from_dockerfile(dockerfile="path", output="path") #this one generates the docker image first
s_container.pull(uri="where the container is", output="path the to sif file to be created")
s_container.push(remote_uri="where to push the file") 
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