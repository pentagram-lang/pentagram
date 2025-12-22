use anyhow::Result as AnyhowResult;
use anyhow::anyhow;
use boot_db::Builtin;
use boot_db::FunctionId;
use boot_db::ResolvedTerm;
use boot_db::ResolvedWord;
use boot_db::Value;
use std::collections::HashMap;
use std::collections::hash_map::RandomState;
use std::fmt;
use std::hash::BuildHasher;
use std::io::Write;
use std::mem;

pub struct VM<'a, S = RandomState> {
  stack: Vec<Value>,
  functions: &'a HashMap<FunctionId, Vec<ResolvedTerm>, S>,
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
    functions: &'a HashMap<FunctionId, Vec<ResolvedTerm>, S>,
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
  terms: &[ResolvedTerm],
) -> AnyhowResult<()> {
  for term in terms {
    step_vm(vm, term.clone())?;
  }
  Ok(())
}

fn step_vm<S: BuildHasher>(
  vm: &mut VM<'_, S>,
  term: ResolvedTerm,
) -> AnyhowResult<()> {
  match term {
    ResolvedTerm::Literal(v) => vm.stack.push(v),
    ResolvedTerm::Word(w) => exec_vm_word(vm, w)?,
  }
  Ok(())
}

fn exec_vm_word<S: BuildHasher>(
  vm: &mut VM<'_, S>,
  word: ResolvedWord,
) -> AnyhowResult<()> {
  match word {
    ResolvedWord::Builtin(b) => exec_vm_builtin(vm, b),
    ResolvedWord::Function(id) => {
      if let Some(body) = vm.functions.get(&id) {
        return eval_vm(vm, body);
      }
      Err(anyhow!("Runtime Error: Function not found: {}", id.0))
    }
  }
}

fn exec_vm_builtin<S: BuildHasher>(
  vm: &mut VM<'_, S>,
  b: Builtin,
) -> AnyhowResult<()> {
  match b {
    Builtin::Add => {
      let b = pop_vm_int(vm)?;
      let a = pop_vm_int(vm)?;
      vm.stack.push(Value::Integer(a + b));
    }
    Builtin::Eq => {
      let b = vm.stack.pop().ok_or_else(|| anyhow!("Stack underflow"))?;
      let a = vm.stack.pop().ok_or_else(|| anyhow!("Stack underflow"))?;
      vm.stack.push(Value::Boolean(a == b));
    }
    Builtin::Say => {
      let v = vm.stack.pop().ok_or_else(|| anyhow!("Stack underflow"))?;
      writeln!(vm.stdout, "{v}").map_err(|e| anyhow!("IO Error: {e}"))?;
    }
    Builtin::Assert => {
      let v = vm.stack.pop().ok_or_else(|| anyhow!("Stack underflow"))?;
      match v {
        Value::Boolean(true) => {}
        Value::Boolean(false) => {
          return Err(anyhow!("Assertion failed"));
        }
        _ => {
          return Err(anyhow!("Expected boolean for assert, got {v:?}"));
        }
      }
    }
  }
  Ok(())
}

fn pop_vm_int<S: BuildHasher>(vm: &mut VM<'_, S>) -> AnyhowResult<i64> {
  let v = vm.stack.pop().ok_or_else(|| anyhow!("Stack underflow"))?;
  match v {
    Value::Integer(i) => Ok(i),
    _ => Err(anyhow!("Expected integer, got {v:?}")),
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
