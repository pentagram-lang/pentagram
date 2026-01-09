use boot_db::Builtin;
use boot_db::Diagnostic;
use boot_db::DiagnosticResult;
use boot_db::FileId;
use boot_db::FunctionId;
use boot_db::ResolvedTerm;
use boot_db::ResolvedWord;
use boot_db::Span;
use boot_db::SpannedResolvedTerm;
use boot_db::Value;
use std::collections::HashMap;
use std::collections::hash_map::RandomState;
use std::fmt;
use std::hash::BuildHasher;
use std::io::Write;
use std::mem;

pub struct VM<'a, S = RandomState> {
  stack: Vec<Value>,
  functions:
    &'a HashMap<FunctionId, (FileId, Vec<SpannedResolvedTerm>), S>,
  stdout: Box<dyn Write + Send + 'a>,
}

impl<S: BuildHasher> fmt::Debug for VM<'_, S> {
  fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
    fmt_vm(self, f)
  }
}

fn fmt_vm<S: BuildHasher>(
  vm: &VM<'_, S>,
  f: &mut fmt::Formatter<'_>,
) -> fmt::Result {
  f.debug_struct("VM")
    .field("stack", &vm.stack)
    .field("functions", &vm.functions)
    .field("stdout", &"<stdout>")
    .finish()
}

impl<'a, S: BuildHasher> VM<'a, S> {
  pub fn new(
    functions: &'a HashMap<
      FunctionId,
      (FileId, Vec<SpannedResolvedTerm>),
      S,
    >,
    stdout: Box<dyn Write + Send + 'a>,
  ) -> Self {
    Self {
      stack: Vec::new(),
      functions,
      stdout,
    }
  }
}

pub fn eval_vm<S: BuildHasher>(
  vm: &mut VM<'_, S>,
  file_id: &FileId,
  terms: &[SpannedResolvedTerm],
) -> DiagnosticResult<()> {
  for term in terms {
    step_vm(vm, file_id, term)?;
  }
  Ok(())
}

fn step_vm<S: BuildHasher>(
  vm: &mut VM<'_, S>,
  file_id: &FileId,
  term: &SpannedResolvedTerm,
) -> DiagnosticResult<()> {
  let span = term.span;
  match &term.value {
    ResolvedTerm::Literal(v) => vm.stack.push(v.clone()),
    ResolvedTerm::Word(w) => {
      exec_vm_word(vm, file_id, w.clone(), span)?;
    }
  }
  Ok(())
}

fn exec_vm_word<S: BuildHasher>(
  vm: &mut VM<'_, S>,
  file_id: &FileId,
  word: ResolvedWord,
  span: Span,
) -> DiagnosticResult<()> {
  match word {
    ResolvedWord::Builtin(b) => exec_vm_builtin(vm, file_id, span, b),
    ResolvedWord::Function(id) => {
      if let Some((func_file_id, body)) = vm.functions.get(&id) {
        return eval_vm(vm, func_file_id, body);
      }
      Err(Diagnostic {
        file_id: file_id.clone(),
        span,
        error_message: format!(
          "Runtime Error: Function not found: {}",
          id.0
        ),
      })
    }
  }
}

fn exec_vm_builtin<S: BuildHasher>(
  vm: &mut VM<'_, S>,
  file_id: &FileId,
  span: Span,
  b: Builtin,
) -> DiagnosticResult<()> {
  match b {
    Builtin::Add => {
      let b = pop_vm_int(vm, file_id, span)?;
      let a = pop_vm_int(vm, file_id, span)?;
      vm.stack.push(Value::Integer(a + b));
    }
    Builtin::Eq => {
      let b = pop_vm(vm, file_id, span)?;
      let a = pop_vm(vm, file_id, span)?;
      vm.stack.push(Value::Boolean(a == b));
    }
    Builtin::Say => {
      let v = pop_vm(vm, file_id, span)?;
      writeln!(vm.stdout, "{v}").map_err(|e| Diagnostic {
        file_id: file_id.clone(),
        span,
        error_message: format!("IO Error: {e}"),
      })?;
    }
    Builtin::Assert => {
      let v = pop_vm(vm, file_id, span)?;
      match v {
        Value::Boolean(true) => {}
        Value::Boolean(false) => {
          return Err(Diagnostic {
            file_id: file_id.clone(),
            span,
            error_message: "Assertion failed".to_string(),
          });
        }
        _ => {
          return Err(Diagnostic {
            file_id: file_id.clone(),
            span,
            error_message: format!(
              "Expected boolean for assert, got {v:?}"
            ),
          });
        }
      }
    }
  }
  Ok(())
}

fn pop_vm<S: BuildHasher>(
  vm: &mut VM<'_, S>,
  file_id: &FileId,
  span: Span,
) -> DiagnosticResult<Value> {
  vm.stack.pop().ok_or_else(|| Diagnostic {
    file_id: file_id.clone(),
    span,
    error_message: "Stack underflow".to_string(),
  })
}

fn pop_vm_int<S: BuildHasher>(
  vm: &mut VM<'_, S>,
  file_id: &FileId,
  span: Span,
) -> DiagnosticResult<i64> {
  let v = pop_vm(vm, file_id, span)?;
  match v {
    Value::Integer(i) => Ok(i),
    _ => Err(Diagnostic {
      file_id: file_id.clone(),
      span,
      error_message: format!("Expected integer, got {v:?}"),
    }),
  }
}

pub fn take_vm_stack<S: BuildHasher>(vm: &mut VM<'_, S>) -> Vec<Value> {
  mem::take(&mut vm.stack)
}

impl<S: BuildHasher> VM<'_, S> {
  pub fn stdout_mut(&mut self) -> &mut dyn Write {
    &mut *self.stdout
  }
}

#[cfg(test)]
#[path = "eval_test.rs"]
mod eval_test;
