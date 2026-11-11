import os
from collections.abc import Sequence


def run_shell(args: Sequence[str]) -> None:
  """
  Runs the boot_shell using cargo run, replacing the current process.
  """
  cmd = ['cargo', 'run', '-p', 'boot_shell', '--', *args]

  # execvp replaces the current process with the new program.
  # Cargo selects the boot_shell package; remaining arguments follow '--'.
  print(f'Exec: {" ".join(cmd)}', flush=True)
  os.execvp('cargo', cmd)
