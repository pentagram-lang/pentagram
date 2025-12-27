use anyhow::Result as AnyhowResult;
use boot_db::FunctionId;
use boot_db::ResolvedTerm;
use boot_db::TestId;
use boot_eval::VM;
use boot_eval::eval_vm;
use std::collections::HashMap;
use std::io::Cursor;
use std::io::Write;

#[derive(Debug, PartialEq, Eq, Clone)]
pub struct TestRunResult {
  pub test_id: TestId,
  pub passed: bool,
  pub output: String,
}

#[derive(Debug)]
pub struct TestInput<'a> {
  pub tests_to_run: &'a [(TestId, Vec<ResolvedTerm>)],
  pub functions: &'a HashMap<FunctionId, Vec<ResolvedTerm>>,
}

#[allow(clippy::print_stdout)]
pub fn run_tests(
  input: &TestInput<'_>,
) -> AnyhowResult<Vec<TestRunResult>> {
  let mut results = Vec::with_capacity(input.tests_to_run.len());

  for (id, body) in input.tests_to_run {
    let mut output = Vec::new();

    let res = {
      let mut vm =
        VM::new(input.functions, Box::new(Cursor::new(&mut output)));

      eval_vm(&mut vm, body)
    };

    if let Err(e) = &res {
      writeln!(Cursor::new(&mut output), "{e}").ok();
    }

    let test_passed = res.is_ok();

    let output_str = String::from_utf8_lossy(&output).to_string();

    results.push(TestRunResult {
      test_id: id.clone(),
      passed: test_passed,
      output: output_str,
    });
  }

  Ok(results)
}

#[cfg(test)]
#[path = "tst_test.rs"]
mod tst_test;
