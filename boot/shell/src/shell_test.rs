use crate::step::step_repl;
use boot_engine::Database;
use std::io::Cursor;

#[test]
fn test_repl_step_basic() {
  let mut db = Database::default();
  let mut output = Vec::new();

  {
    let mut cursor = Cursor::new(&mut output);
    step_repl(&mut db, "def foo fn 42 end-fn, foo", &mut cursor)
      .expect("Step failed");
  }

  let out_str = String::from_utf8(output).expect("Invalid UTF-8");
  assert_eq!(out_str, "[ 42 ]\n");

  let mut output2 = Vec::new();
  {
    let mut cursor = Cursor::new(&mut output2);
    step_repl(&mut db, "foo 1 +", &mut cursor).expect("Step failed");
  }

  let out_str2 = String::from_utf8(output2).expect("Invalid UTF-8");
  assert_eq!(out_str2, "[ 43 ]\n");
}

#[test]
fn test_repl_step_redefine() {
  let mut db = Database::default();
  let mut output = Vec::new();

  {
    let mut cursor = Cursor::new(&mut output);
    step_repl(&mut db, "def foo fn 42 end-fn, foo", &mut cursor)
      .expect("Step 1 failed");
  }
  assert_eq!(String::from_utf8(output.clone()).unwrap(), "[ 42 ]\n");

  output.clear();
  {
    let mut cursor = Cursor::new(&mut output);
    step_repl(&mut db, "def foo fn 100 end-fn, foo", &mut cursor)
      .expect("Step 2 failed");
  }
  assert_eq!(String::from_utf8(output.clone()).unwrap(), "[ 100 ]\n");

  output.clear();
  {
    let mut cursor = Cursor::new(&mut output);
    step_repl(&mut db, "foo", &mut cursor).expect("Step 3 failed");
  }
  assert_eq!(String::from_utf8(output.clone()).unwrap(), "[ 100 ]\n");
}

#[test]
fn test_repl_syntax_error() {
  let mut db = Database::default();
  let mut output = Vec::new();

  {
    let mut cursor = Cursor::new(&mut output);
    step_repl(&mut db, "def f 2 end-fn,", &mut cursor)
      .expect("Step failed");
  }

  let out_str = String::from_utf8(output).expect("Invalid UTF-8");
  assert_eq!(out_str, "            ^\n      expected 'fn'\n");
}

#[test]
fn test_repl_step_error() {
  let mut db = Database::default();
  let mut output = Vec::new();

  {
    let mut cursor = Cursor::new(&mut output);
    step_repl(&mut db, "unknown_word", &mut cursor).expect("Step failed");
  }

  let out_str = String::from_utf8(output).expect("Invalid UTF-8");
  assert_eq!(out_str, "Error: Undefined reference: unknown_word\n");
}
