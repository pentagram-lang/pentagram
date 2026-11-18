use super::*;
use std::env::temp_dir;
use std::fs::create_dir_all;
use std::fs::remove_dir_all;
use std::fs::write;
use std::io::Cursor;
use std::process::id as process_id;
use std::sync::atomic::AtomicU64;
use std::sync::atomic::Ordering;
use std::time::SystemTime;
use std::time::UNIX_EPOCH;

static NEXT_TEMP_ID: AtomicU64 = AtomicU64::new(0);

struct TempDir {
  path: PathBuf,
}

impl TempDir {
  fn new(prefix: &str) -> Self {
    let shm = Path::new("/dev/shm");
    let base = if shm.is_dir() {
      shm.to_path_buf()
    } else {
      temp_dir()
    };
    let nanos = SystemTime::now()
      .duration_since(UNIX_EPOCH)
      .expect("System clock before epoch")
      .as_nanos();
    let seq = NEXT_TEMP_ID.fetch_add(1, Ordering::Relaxed);
    let pid = process_id();
    let path = base.join(format!("{prefix}-{pid}-{nanos}-{seq}"));
    create_dir_all(&path).expect("Create temp dir");
    Self { path }
  }
}

impl Drop for TempDir {
  fn drop(&mut self) {
    if remove_dir_all(&self.path).is_err() {}
  }
}

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
  assert_eq!(
    out_str,
    "Error: expected 'fn'\n  def f 2 end-fn,\n        ^\n"
  );
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
  assert_eq!(
    out_str,
    "Error: Undefined reference: unknown_word\n  unknown_word\n  ^\n"
  );
}

#[test]
fn test_repl_error_previous_input() {
  let mut db = Database::default();
  let mut output = Vec::new();

  {
    let mut cursor = Cursor::new(&mut output);
    step_repl(&mut db, "def boom fn 1 2 eq assert end-fn", &mut cursor)
      .expect("Step 1 failed");
  }

  output.clear();

  {
    let mut cursor = Cursor::new(&mut output);
    step_repl(&mut db, "boom", &mut cursor).expect("Step 2 failed");
  }

  let out_str = String::from_utf8(output).expect("Invalid UTF-8");

  assert_eq!(
    out_str,
    "Error: Assertion failed\n  In repl:1:\n  def boom fn 1 2 eq assert end-fn\n                     ^\n"
  );
}

#[tokio::test]
async fn test_run_harness_directory_cross_file() {
  let dir = TempDir::new("pentagram-shell-cross");
  let math_path = dir.path.join("math.penta");
  let test_path = dir.path.join("math.test.penta");

  write(&math_path, "def add fn\n  +\nend-fn,\n")
    .expect("Write math.penta");
  write(&test_path, "test\n  1 1 add 2 eq assert\nend-test,\n")
    .expect("Write math.test.penta");

  let mut db = Database::default();
  let mut output = Vec::new();
  run_harness(&mut db, &dir.path, &mut output)
    .await
    .expect("Harness failed");

  let out_str = String::from_utf8(output).expect("Invalid UTF-8");
  let expected = format!("PASS {}.0\n", test_path.display());
  assert_eq!(out_str, expected);
}

#[tokio::test]
async fn test_run_harness_directory_no_duplicate_pass() {
  let dir = TempDir::new("pentagram-shell-batch");
  let first_path = dir.path.join("a.test.penta");
  let second_path = dir.path.join("b.test.penta");

  write(&first_path, "test\n  1 1 eq assert\nend-test,\n")
    .expect("Write a.test.penta");
  write(&second_path, "test\n  2 2 eq assert\nend-test,\n")
    .expect("Write b.test.penta");

  let mut db = Database::default();
  let mut output = Vec::new();
  run_harness(&mut db, &dir.path, &mut output)
    .await
    .expect("Harness failed");

  let out_str = String::from_utf8(output).expect("Invalid UTF-8");
  let expected = format!(
    "PASS {}.0\nPASS {}.0\n",
    first_path.display(),
    second_path.display()
  );
  assert_eq!(out_str, expected);
}

#[tokio::test]
async fn test_run_harness_directory_empty() {
  let dir = TempDir::new("pentagram-shell-empty");
  let mut db = Database::default();
  let mut output = Vec::new();
  run_harness(&mut db, &dir.path, &mut output)
    .await
    .expect("Harness failed");

  assert!(output.is_empty());
}

#[tokio::test]
async fn test_run_harness_directory_incremental_edit() {
  let dir = TempDir::new("pentagram-shell-incremental");
  let math_path = dir.path.join("math.penta");
  let test_path = dir.path.join("math.test.penta");

  write(&math_path, "def add fn\n  +\nend-fn,\n")
    .expect("Write math.penta");
  write(&test_path, "test\n  1 1 add 2 eq assert\nend-test,\n")
    .expect("Write math.test.penta");

  let mut db = Database::default();
  let mut output = Vec::new();
  run_harness(&mut db, &dir.path, &mut output)
    .await
    .expect("Initial harness failed");

  let expected = format!("PASS {}.0\n", test_path.display());
  assert_eq!(String::from_utf8(output.clone()).unwrap(), expected);

  write(&test_path, "test\n  2 3 add 5 eq assert\nend-test,\n")
    .expect("Update math.test.penta");
  output.clear();
  run_harness(&mut db, &dir.path, &mut output)
    .await
    .expect("Incremental harness failed");

  assert_eq!(String::from_utf8(output).unwrap(), expected);
}
