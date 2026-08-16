use boot_db::FileId;
use boot_db::FunctionId;
use boot_db::SpannedResolvedTerm;
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
  pub tests_to_run: &'a [(TestId, FileId, Vec<SpannedResolvedTerm>)],
  pub functions:
    &'a HashMap<FunctionId, (FileId, Vec<SpannedResolvedTerm>)>,
}

#[allow(clippy::print_stdout)]
pub fn run_tests(input: &TestInput<'_>) -> Vec<TestRunResult> {
  let mut results = Vec::with_capacity(input.tests_to_run.len());

  for (id, file_id, body) in input.tests_to_run {
    let mut output = Vec::new();

    let res = {
      let mut vm =
        VM::new(input.functions, Box::new(Cursor::new(&mut output)));

      eval_vm(&mut vm, file_id, body)
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

  results
}

#[cfg(test)]
#[path = "tst_test.rs"]
mod tst_test;
