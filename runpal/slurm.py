import re
import os
import posixpath
import stat
from contextlib import contextmanager
from functools import wraps
from typing import Optional

import openapi_slurm

import jwt
import paramiko
from jwt.exceptions import ExpiredSignatureError


class SlurmRunner:
    """
    Slurm Runner class for managing Slurm job submissions.

    This class allows you to interact with the HPC remotely (eg. from a VM).
    It uses a mixture of SSH and REST API access to run generic scripts.

    IMPORTANT:
    This class has file I/O and exec function on HPC.
    Do not expose this functionality to user-generated input in any capacity,
    as this will introduce a serious security vulnerability.

    All scripts or backend code that use this class must only accept inputs that
    are provided by developers or trusted sources.
    """

    DEFAULT_TOKEN_LIFESPAN = 60 * 60 * 24 * 7  # 7 days in seconds

    def __init__(
            self,
            api_host: str,
            hpc_host: str,
            username: str,
            password: str,
            token_lifespan: int = DEFAULT_TOKEN_LIFESPAN,
    ):
        """
        Create a slurm runner.

        Args:
            api_host (str): The host IP address or domain name for the Slurm REST API. Example: "slurm-api.example.com"
            hpc_host (str): The host IP address or domain name for HPC login nodes. Example: "slogin.example.com"
            username (str): The username for connecting to the HPC cluster / Slurm.
            password (str): The password for connecting to HPC / Slurm. Needed for JWT token fetch.
            api_version (str, optional): The API version for Slurm API. Defaults to "".
        """
        self.api_host = api_host
        self.hpc_host = hpc_host
        self.username = username
        self.password = password

        self.token_lifespan = token_lifespan

        self.token = None

    def get_new_jwt(self):
        """Fetch a fresh JWT using an SSH connection to HPC. Set self.token if successful.

        Raises:
            TokenFetchError: Failed to extract the JWT from the output from `scontrol token`

        Returns:
            (str | None): The new token fetched from HPC, or None if unsuccessful.
        """
        token = None
        with paramiko.SSHClient() as client:
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                hostname=self.hpc_host,
                username=self.username,
                password=self.password,
            )
            _, stdout, _ = client.exec_command(
                f"scontrol token lifespan={self.token_lifespan}"
            )

            # expected result: SLURM_JWT={token}
            output = stdout.read().decode()
            pattern = re.compile(r"^SLURM_JWT=(.+)$")
            match = re.search(pattern, output)
            if match:
                token = match.group(1)
                try:
                    jwt.decode(token, options={"verify_signature": False})
                except jwt.DecodeError:
                    print("Invalid JWT")
            else:
                raise TokenFetchError("couldn't match to jwt")

        if token is not None:
            self.token = token
        return token

    @staticmethod
    def _handle_jwt(func):
        """Decorator function to automatically refetch a JWT for REST API access.
        Should be used to decorate any function that uses the REST API.

        Args:
            func (Callable): A method within this class that performs a request to the Slurm REST API.

        Returns:
            Callable: Wrapped method that will handle JWT refresh for you.
        """

        @wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                assert self.token is not None
                jwt.decode(self.token, options={"verify_signature": False})
            except Exception as e:  # pylint: disable=W0718
                if any(
                        isinstance(e, err_type)
                        for err_type in [AssertionError, ExpiredSignatureError]
                ):
                    self.get_new_jwt()
                else:
                    # genuine error
                    raise e

            return func(*args, **kwargs)

        return wrapper

    @_handle_jwt
    def get_configuration(self):
        """
        Get openapi_slurm configuration for this runner.
        """
        configuration = openapi_slurm.Configuration(
            host=f"https://{self.api_host}"
        )
        configuration.api_key["user"] = self.username
        configuration.api_key["token"] = self.token or ""

        return configuration

    @contextmanager
    def get_ssh_client(self):
        """
        Create and yield a paramiko SSH client.
        """
        client = paramiko.SSHClient()
        try:
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                hostname=self.hpc_host,
                username=self.username,
                password=self.password,
            )
            yield client
        finally:
            client.close()

    def send_file(
            self,
            local_path: os.PathLike,
            remote_path: str,
            force: bool = False,
            remote_working_directory: Optional[str] = None,
    ):
        """Send a file from the local filesystem to the HPC filesystem.

        Args:
            local_path      (os.PathLike): Path to a file on the local filesystem. Must be a single file.
            remote_path             (str): Path on HPC where the file will be transferred.
                                           If it's a directory, then src file basename will be added.
            force                  (bool): If True, will overwrite remote file if it already exists. Defaults to False.
            remote_working_directory  (str | None): Optional, absolute path to working directory on HPC.
        Raises:
            FileNotFoundError: If local_path is not a valid file.
            IsADirectoryError: If local_path is a directory.
            FileExistsError: If remote_path already exists and Force is false.
        """
        if not os.path.exists(local_path):
            raise FileNotFoundError(local_path)

        if os.path.isdir(local_path):
            raise IsADirectoryError(local_path)

        # rudamentary 'is this a dir' check
        if remote_path[-1] == "/":
            remote_path += os.path.basename(local_path)

        with self.get_ssh_client() as client:
            with client.open_sftp() as sftp:
                if remote_working_directory is not None:
                    sftp.chdir(remote_working_directory)
                try:
                    sftp.stat(remote_path)
                    if not force:
                        raise FileExistsError
                except FileNotFoundError:
                    pass
                sftp.put(local_path, remote_path)

    def create_directory(self, name: str, remote_path: str, exists_ok: bool = False, follow_symlinks: bool = True):
        """
        Create a directory on the remote file system if force it will just i
        :param name: The name of the directory to create.
        :param remote_path: where to create the directory.
        :param exists_ok: (bool) If True, it will not raise and error if the directory already exists
        :return: None
        Raises:
        IsADirectoryError: If remote_path already exists and exists_ok is false.
        DirectoryNotFoundError: If remote_path does not exist.
        """
        with self.get_ssh_client() as client:
            with client.open_sftp() as sftp:
                try:
                    st_parent = sftp.stat(remote_path) if follow_symlinks else sftp.lstat(remote_path)
                except FileNotFoundError:
                    raise FileNotFoundError(f"Parent path does not exist: {remote_path}")
                except IOError as e:
                    if getattr(e, "errno", None) == 2:
                        raise FileNotFoundError(f"Parent path does not exist: {remote_path}") from e
                    raise
                if not stat.S_ISDIR(st_parent.st_mode):
                    raise NotADirectoryError(f"Parent path is not a directory: {remote_path}")

                target = posixpath.join(remote_path, name)

                try:
                    st_target = sftp.stat(target) if follow_symlinks else sftp.lstat(target)
                    if stat.S_ISDIR(st_target.st_mode):
                        if exists_ok:
                            print(f"Directory already exists: {target}")
                            return target
                        raise FileExistsError(f"Directory already exists: {target}")
                    else:
                        raise FileExistsError(f"Path exists and is not a directory: {target}")
                except FileNotFoundError:
                    pass
                except IOError as e:
                    if getattr(e, "errno", None) == 2:
                        pass
                    else:
                        raise
                try:
                    sftp.mkdir(target)
                except IOError as e:
                    if getattr(e, "errno", None) in (17,):  # EEXIST
                        if exists_ok:
                            print(f"Directory already exists: {target}")
                            return target
                        raise FileExistsError(f"Directory already exists: {target}") from e
                    raise
                return f"Created {target}"

    def receive_file(
            self,
            remote_path: str,
            local_path: str,
            force: bool = False,
            remote_working_directory: Optional[str] = None,
    ):
        """Download a file from HPC onto the local file system.

        Args:
            remote_path      (str): Remote filepath on HPC to transfer to local.
            local_path       (str): Local filepath to save HPC file. Can be file name or directory.
            force (bool, optional): If True, overwrites local_path if it already exists. Defaults to False.

        Raises:
            FileExistsError: Raised if local_path already exists and force is False, to prevent overwriting.
        """

        if os.path.exists(local_path) and os.path.isfile(local_path) and not force:
            raise FileExistsError(local_path)

        if os.path.isdir(local_path):
            local_path = os.path.join(local_path, os.path.basename(remote_path))

        with self.get_ssh_client() as client:
            with client.open_sftp() as sftp:
                if remote_working_directory is not None:
                    sftp.chdir(remote_working_directory)
                sftp.get(remote_path, local_path)

    def run_job(self, cmd: str, working_dir: str | None = None, options: dict | None = None):
        """Run a job on Slurm.

        Args:
            cmd (str): Script command to run.
            working_dir (str | None): Working directory on HPC to run the script from.
            options (dict | None): Slurm Job options. See: https://github.com/ccmbioinfo/openapi-slurm/blob/main/docs/V0043JobDescMsg.md

        Returns:
            (int | None): Job ID of newly-submitted job, or None if unsuccessful.
        """
        if options is None:
            options = {}

        if working_dir is not None:
            options["current_working_directory"] = working_dir

        with openapi_slurm.ApiClient(self.get_configuration()) as client:
            api_instance = openapi_slurm.SlurmApi(client)
            job = SlurmJob(
                script=cmd,
                **options,
            )
            request = JobSubmitRequest(job=job)
            api_response = api_instance.slurm_v0043_post_job_submit(v0043_job_submit_req=request)
        return api_response.job_id

    def run_job_ssh(self, script_path: str, working_dir: str | None = None, options: dict | None = None):
        """Run a job on Slurm via SSH connection by running 'sbatch' on the provided script_path.

        Args:
            script_path (str): Path to script on HPC to execute using 'sbatch'.
            working_dir (str | None): Working directory to execute from on HPC. Defaults to None.
            options (dict | None): Dictionary of 'sbatch' options to include with the command.
                                   Example:
                                   ```
                                   {
                                       "--mem": "2G",
                                       "-t": "2:00:00",
                                       "--cpus-per-task": "1",
                                   }
                                   ```

        Returns:
            (int | None): Job ID of newly-submitted job, or None if unsuccessful.
        """
        if options is None:
            options = {}

        # build full command
        cmd = ""
        if working_dir is not None:
            cmd += f"cd {working_dir}; sbatch "
        for key in options:
            cmd += f"{key} {options[key]} "
        cmd += script_path

        with self.get_ssh_client() as client:
            stdin, stdout, stderr = client.exec_command(cmd)
            try:
                match = re.search(re.compile(r" (\d+)$"), stdout.read().decode())  # type: ignore
                job_id = int(match.group(1))
            except IndexError as e:
                job_id = None

        return job_id

    def run_command(self, cmd):
        with self.get_ssh_client() as client:
            stdin, stdout, stderr = client.exec_command(cmd)
        return stdin, stdout, stderr