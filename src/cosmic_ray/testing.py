"Support for running tests in a subprocess."

import logging
import os
import shlex
import subprocess
import traceback

from cosmic_ray.work_item import TestOutcome

log = logging.getLogger(__name__)

# We use an asyncio-subprocess-based approach here instead of a simple
# subprocess.run()-based approach because there are problems with timeouts and
# reading from stderr in subprocess.run. Since we have to be prepared for test
# processes that run longer than timeout (and, indeed, which run forever), the
# broken subprocess stuff simply doesn't work. So we do this, which seems to
# work on all platforms.


def run_tests(command, timeout):
    """Run test command in a subprocess.

    If the command exits with status 0, then we assume that all tests passed. If
    it exits with any other code, we assume a test failed. If the call to launch
    the subprocess throws an exception, we consider the test 'incompetent'.

    Tests which time out are considered 'killed' as well.

    Args:
        command (str): The command to execute.
        timeout (number): The maximum number of seconds to allow the tests to run.

    Return: A tuple `(TestOutcome, output)` where the `output` is a string
        containing the output of the command.
    """
    log.info("Running test (timeout=%s): %s", timeout, command)

    split_command = command.split(' ')
    report_arg_index = [i for i, x in enumerate(split_command) if '--report=' in x][0]
    report_arg = split_command[report_arg_index]
    report_name = report_arg[9:]
    job_id_arg = [i for i in split_command if '--job_id' in i][0]
    job_id = job_id_arg[9:]
    prefix=report_name[:-5]
    extension = report_name[-5:]
    report_name_with_job_id = f"{prefix}_{job_id}{extension}"
    report_arg_new = f"--report={report_name_with_job_id}"
    split_command.remove(job_id_arg)
    split_command[report_arg_index] = report_arg_new
    new_command = ' '.join(split_command)
    command = new_command

    # We want to avoid writing pyc files in case our changes happen too fast for Python to
    # notice them. If the timestamps between two changes are too small, Python won't recompile
    # the source.
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    try:
        proc = subprocess.run(shlex.split(command), check=True, env=env, timeout=timeout, capture_output=True)
        assert proc.returncode == 0
        return (TestOutcome.SURVIVED, proc.stdout.decode("utf-8"))

    except subprocess.CalledProcessError as err:
        return (TestOutcome.KILLED, err.output.decode("utf-8"))

    except subprocess.TimeoutExpired:
        return (TestOutcome.KILLED, "timeout")

    except Exception:  # pylint: disable=W0703
        return (TestOutcome.INCOMPETENT, traceback.format_exc())
