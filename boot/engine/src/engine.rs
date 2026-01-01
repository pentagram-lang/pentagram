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
use boot_db::Database;
use boot_db::DiagnosticResult;
use boot_db::ResolvedDiagnosticResult;
use boot_eval::VM;
use boot_eval::take_vm_stack;
use std::io::Write;

pub fn execute_file(
  db: &mut Database,
  path: &str,
  content: &str,
  output: &mut (dyn Write + Send),
) -> ResolvedDiagnosticResult<()> {
  let result: DiagnosticResult<()> = (|| {
    shred_file(db, path, content)?;
    resolve_module(db)?;
    analyze_dependencies(db);
    run_statements(db, path, output)?;
    run_main(db, output)?;
    Ok(())
  })();

  if let Err(diagnostic) = result {
    let resolved = diagnostic.resolve(db);
    rollback_engine_generation(db);
    Err(resolved)
  } else {
    commit_engine_generation(db);
    Ok(())
  }
}

pub fn execute_repl(
  db: &mut Database,
  line: &str,
  output: &mut (dyn Write + Send),
) -> ResolvedDiagnosticResult<()> {
  let result: DiagnosticResult<()> = (|| {
    let module = shred_repl(db, line)?;

    resolve_module(db)?;
    analyze_dependencies(db);

    let functions_map = get_engine_functions_map(db);
    let mut vm = VM::new(&functions_map, Box::new(output));

    if !module.statements.is_empty() {
      let file_id = db
        .files
        .iter()
        .rfind(|f| f.id.0.starts_with("repl:"))
        .map(|f| f.id.clone())
        .expect("REPL file not found after shredding");

      run_statements_on_vm(db, &file_id.0, &mut vm)?;
    }

    let stack = take_vm_stack(&mut vm);

    if !stack.is_empty() {
      write!(vm.stdout_mut(), "[").expect("REPL IO failure");
      for v in stack {
        write!(vm.stdout_mut(), " {v}").expect("REPL IO failure");
      }
      writeln!(vm.stdout_mut(), " ]").expect("REPL IO failure");
    }
    Ok(())
  })();

  if let Err(diagnostic) = result {
    let resolved = diagnostic.resolve(db);
    rollback_engine_generation(db);
    Err(resolved)
  } else {
    commit_engine_generation(db);
    Ok(())
  }
}

pub fn execute_tests(
  db: &mut Database,
  files: &[(&str, &str)],
  output: &mut (dyn Write + Send),
) -> ResolvedDiagnosticResult<()> {
  let result: DiagnosticResult<()> = (|| {
    for (path, content) in files {
      shred_file(db, path, content)?;
    }
    resolve_module(db)?;
    analyze_dependencies(db);
    run_engine_tests_incrementally(db);

    let mut results: Vec<_> = db
      .test_results
      .iter()
      .filter(|r| r.generation.is_new())
      .collect();

    results.sort_by(|a, b| a.id.0.cmp(&b.id.0));

    for res in results {
      let status = if res.passed { "PASS" } else { "FAIL" };
      writeln!(output, "{} {}", status, res.id.0)
        .expect("Test output failure");
      if !res.passed {
        write!(output, "{}", res.output).expect("Test output failure");
      }
    }

    Ok(())
  })();

  if let Err(diagnostic) = result {
    let resolved = diagnostic.resolve(db);
    rollback_engine_generation(db);
    Err(resolved)
  } else {
    commit_engine_generation(db);
    Ok(())
  }
}

#[cfg(test)]
#[path = "engine_test.rs"]
mod engine_test;
