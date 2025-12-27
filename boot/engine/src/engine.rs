use crate::analyze::analyze_dependencies;
use crate::execute::run_main;
use crate::execute::run_statements;
use crate::execute::run_statements_on_vm;
use crate::generation::commit_engine_generation;
use crate::generation::rollback_engine_generation;
use crate::resolve::resolve_module;
use crate::shred::shred_file;
use crate::shred::shred_repl;
use crate::tst::get_engine_functions_map;
use crate::tst::run_engine_tests_incrementally;
use anyhow::Result as AnyhowResult;
use boot_db::Database;
use boot_db::FileId;
use boot_eval::VM;
use boot_eval::take_vm_stack;
use boot_parse::parse_repl_module;
use std::io::Write;

pub fn execute_file(
  db: &mut Database,
  path: &str,
  content: &str,
  output: &mut (dyn Write + Send),
) -> AnyhowResult<()> {
  let result = (|| {
    shred_file(db, path, content)?;
    resolve_module(db)?;
    analyze_dependencies(db)?;
    run_statements(db, path, output)?;
    run_main(db, output)?;
    Ok(())
  })();

  if result.is_err() {
    rollback_engine_generation(db);
  } else {
    commit_engine_generation(db);
  }

  result
}

pub fn execute_repl(
  db: &mut Database,
  line: &str,
  output: &mut (dyn Write + Send),
) -> AnyhowResult<()> {
  let result = (|| {
    let file_id = FileId("repl".to_string());
    let old_functions: Vec<_> = db
      .functions
      .iter()
      .filter(|f| f.file_id == file_id)
      .cloned()
      .collect();
    let old_tests: Vec<_> = db
      .tests
      .iter()
      .filter(|t| t.file_id == file_id)
      .cloned()
      .collect();

    let module =
      parse_repl_module("repl", old_functions, old_tests, line)?;
    shred_repl(db, module.clone());

    resolve_module(db)?;
    analyze_dependencies(db)?;

    let functions_map = get_engine_functions_map(db);
    let mut vm = VM::new(&functions_map, Box::new(output));

    if !module.statements.is_empty() {
      run_statements_on_vm(db, "repl", &mut vm)?;
    }

    let stack = take_vm_stack(&mut vm);

    if !stack.is_empty() {
      write!(vm.stdout_mut(), "[")?;
      for v in stack {
        write!(vm.stdout_mut(), " {v}")?;
      }
      writeln!(vm.stdout_mut(), " ]")?;
    }
    Ok(())
  })();

  if result.is_err() {
    rollback_engine_generation(db);
  } else {
    commit_engine_generation(db);
  }

  result
}

pub fn execute_tests(
  db: &mut Database,
  files: &[(&str, &str)],
  output: &mut (dyn Write + Send),
) -> AnyhowResult<()> {
  let result = (|| {
    for (path, content) in files {
      shred_file(db, path, content)?;
    }
    resolve_module(db)?;
    analyze_dependencies(db)?;
    run_engine_tests_incrementally(db)?;

    let mut results: Vec<_> = db
      .test_results
      .iter()
      .filter(|r| r.generation.is_new())
      .collect();

    results.sort_by(|a, b| a.id.0.cmp(&b.id.0));

    for res in results {
      let status = if res.passed { "PASS" } else { "FAIL" };
      writeln!(output, "{} {}", status, res.id.0)?;
      if !res.passed {
        write!(output, "{}", res.output)?;
      }
    }

    Ok(())
  })();

  if result.is_err() {
    rollback_engine_generation(db);
  } else {
    commit_engine_generation(db);
  }

  result
}

#[cfg(test)]
#[path = "engine_test.rs"]
mod engine_test;
