import os


def run_shell(args):
  """
  Runs the boot_shell using cargo run, replacing the current process.
  """
  # boot/shell is the package 'shell' in the cargo workspace.
  # We use 'cargo run -p shell' to run it.
  cmd = ['cargo', 'run', '-p', 'boot_shell', '--'] + list(args)

  # execvp replaces the current process with the new program.
  # The first argument is the file to execute (cargo), the second is the
  # list of arguments (including the command name).
  print(f'Exec: {" ".join(cmd)}')
  os.execvp('cargo', cmd)
