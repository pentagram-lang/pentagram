"""Tests for zero.boot."""

import os
import sys

import click
import pytest

from zero import boot


class _RecordingStdout:
  """In-memory stdout recorder tracking writes, flushes, and execs."""

  def __init__(self, *, flush_error: OSError | None = None) -> None:
    self.events: list[tuple[str, object]] = []
    self._flush_error = flush_error

  def write(self, text: str) -> int:
    self.events.append(('write', text))
    return len(text)

  def flush(self) -> None:
    self.events.append(('flush', None))
    if self._flush_error is not None:
      raise self._flush_error

  def record_exec(self, file: str, args: list[str]) -> None:
    self.events.append(('execvp', (file, list(args))))


def test_build_shell_command() -> None:
  assert boot.build_shell_command([]) == [
    'cargo',
    'run',
    '-p',
    'boot_shell',
    '--',
  ]
  assert boot.build_shell_command(['--check', 'demo.pg']) == [
    'cargo',
    'run',
    '-p',
    'boot_shell',
    '--',
    '--check',
    'demo.pg',
  ]


def test_format_exec_announcement_quotes_and_sanitizes_args() -> None:
  cmd = [
    'cargo',
    'run',
    '-p',
    'boot_shell',
    '--',
    '',
    'arg with spaces',
    os.fsdecode(b'bad-\xff-arg'),
  ]
  formatted = boot.format_exec_announcement(cmd)
  assert formatted == (
    "Exec: cargo run -p boot_shell -- '' 'arg with spaces' "
    "'bad-\\udcff-arg'"
  )
  formatted.encode('utf-8')


def test_run_shell_flushes_announcement_before_execvp(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  recorder = _RecordingStdout()
  monkeypatch.setattr(sys, 'stdout', recorder)
  monkeypatch.setattr(os, 'execvp', recorder.record_exec)

  boot.run_shell(['--trace', 'hello world.pg'])

  expected_cmd = [
    'cargo',
    'run',
    '-p',
    'boot_shell',
    '--',
    '--trace',
    'hello world.pg',
  ]
  assert recorder.events == [
    (
      'write',
      "Exec: cargo run -p boot_shell -- --trace 'hello world.pg'",
    ),
    ('write', '\n'),
    ('flush', None),
    ('execvp', ('cargo', expected_cmd)),
  ]


def test_run_shell_wraps_flush_and_execvp_os_errors(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  failing_stdout = _RecordingStdout(
    flush_error=BrokenPipeError(32, 'broken pipe')
  )
  with monkeypatch.context() as mp:
    mp.setattr(sys, 'stdout', failing_stdout)
    mp.setattr(os, 'execvp', failing_stdout.record_exec)
    with pytest.raises(click.ClickException) as flush_err:
      boot.run_shell([])
    assert str(flush_err.value) == (
      'Failed to launch boot_shell: [Errno 32] broken pipe'
    )

  ok_stdout = _RecordingStdout()
  with monkeypatch.context() as mp:
    mp.setattr(sys, 'stdout', ok_stdout)
    mp.setattr(
      os,
      'execvp',
      lambda *_a: (_ for _ in ()).throw(
        FileNotFoundError(2, os.fsdecode(b'cargo-\xff'))
      ),
    )
    with pytest.raises(click.ClickException) as exec_err:
      boot.run_shell([])
    assert str(exec_err.value) == (
      'Failed to launch boot_shell: [Errno 2] cargo-\\udcff'
    )
