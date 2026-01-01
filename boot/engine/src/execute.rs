use crate::tst::get_engine_functions_map;
use boot_db::Database;
use boot_db::DiagnosticResult;
use boot_db::FileId;
use boot_db::FunctionId;
use boot_eval::VM;
use boot_eval::eval_vm;
use std::io::Write;

pub(crate) fn run_main(
  db: &mut Database,
  output: &mut (dyn Write + Send),
) -> DiagnosticResult<()> {
  if let Some(main_func) = db
    .resolved_functions
    .iter()
    .filter(|f| f.generation.is_new())
    .find(|f| f.id == FunctionId("main".to_string()))
  {
    let functions_map = get_engine_functions_map(db);
    let mut vm = VM::new(&functions_map, Box::new(output));
    eval_vm(&mut vm, &main_func.file_id, &main_func.body)?;
  }
  Ok(())
}

pub(crate) fn run_statements(
  db: &mut Database,
  path: &str,
  output: &mut (dyn Write + Send),
) -> DiagnosticResult<()> {
  let functions_map = get_engine_functions_map(db);
  let mut vm = VM::new(&functions_map, Box::new(output));
  run_statements_on_vm(db, path, &mut vm)
}

pub(crate) fn run_statements_on_vm(
  db: &Database,
  path: &str,
  vm: &mut VM<'_>,
) -> DiagnosticResult<()> {
  let file_id = FileId(path.to_string());
  let mut statements: Vec<_> = db
    .resolved_statements
    .iter()
    .filter(|s| s.generation.is_new() && s.file_id == file_id)
    .collect();

  if statements.is_empty() {
    return Ok(());
  }

  statements.sort_by_key(|s| s.index);

  for stmt in statements {
    eval_vm(vm, &stmt.file_id, &stmt.body)?;
  }

  Ok(())
}

#[cfg(test)]
#[path = "execute_test.rs"]
mod execute_test;
