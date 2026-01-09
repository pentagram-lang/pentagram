use super::*;
use boot_db::FileId;
use boot_db::FunctionId;
use boot_db::ResolvedTerm;
use boot_db::ResolvedWord;
use boot_db::Span;
use boot_db::Spanned;
use pretty_assertions::assert_eq;
use std::io::Cursor;

fn s<T>(val: T) -> Spanned<T> {
  Spanned::new(val, Span { start: 0, end: 0 })
}

#[test]
fn test_arithmetic() {
  let functions = HashMap::new();
  let mut output = Vec::new();
  let mut vm = VM::new(&functions, Box::new(Cursor::new(&mut output)));
  let file_id = FileId("test".to_string());
  eval_vm(
    &mut vm,
    &file_id,
    &[
      s(ResolvedTerm::Literal(Value::Integer(1))),
      s(ResolvedTerm::Literal(Value::Integer(2))),
      s(ResolvedTerm::Word(ResolvedWord::Builtin(Builtin::Add))),
    ],
  )
  .expect("Arithmetic should succeed");
  assert_eq!(take_vm_stack(&mut vm), vec![Value::Integer(3)]);
}

#[test]
fn test_def_call() {
  let file_id = FileId("test".to_string());
  let mut functions = HashMap::new();
  functions.insert(
    FunctionId("inc".to_string()),
    (
      file_id.clone(),
      vec![
        s(ResolvedTerm::Literal(Value::Integer(1))),
        s(ResolvedTerm::Word(ResolvedWord::Builtin(Builtin::Add))),
      ],
    ),
  );

  let mut output = Vec::new();
  let mut vm = VM::new(&functions, Box::new(Cursor::new(&mut output)));
  eval_vm(
    &mut vm,
    &file_id,
    &[
      s(ResolvedTerm::Literal(Value::Integer(10))),
      s(ResolvedTerm::Word(ResolvedWord::Function(FunctionId(
        "inc".to_string(),
      )))),
    ],
  )
  .expect("Function call should succeed");
  assert_eq!(take_vm_stack(&mut vm), vec![Value::Integer(11)]);
}

#[test]
fn test_assert() {
  let functions = HashMap::new();
  let mut output = Vec::new();
  let mut vm = VM::new(&functions, Box::new(Cursor::new(&mut output)));
  let file_id = FileId("test".to_string());
  let err = eval_vm(
    &mut vm,
    &file_id,
    &[
      s(ResolvedTerm::Literal(Value::Integer(1))),
      s(ResolvedTerm::Literal(Value::Integer(2))),
      s(ResolvedTerm::Word(ResolvedWord::Builtin(Builtin::Eq))),
      s(ResolvedTerm::Word(ResolvedWord::Builtin(Builtin::Assert))),
    ],
  )
  .expect_err("Assert should fail for non-equal values");
  assert_eq!(err.error_message, "Assertion failed");
}
