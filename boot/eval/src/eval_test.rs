use super::*;
use boot_db::FunctionId;
use boot_db::ResolvedTerm;
use boot_db::ResolvedWord;
use pretty_assertions::assert_eq;
use std::io::Cursor;

#[test]
fn test_arithmetic() {
  let functions = HashMap::new();
  let mut output = Vec::new();
  let mut vm = VM::new(&functions, Box::new(Cursor::new(&mut output)));
  eval_vm(
    &mut vm,
    &[
      ResolvedTerm::Literal(Value::Integer(1)),
      ResolvedTerm::Literal(Value::Integer(2)),
      ResolvedTerm::Word(ResolvedWord::Builtin(Builtin::Add)),
    ],
  )
  .expect("Arithmetic should succeed");
  assert_eq!(take_vm_stack(&mut vm), vec![Value::Integer(3)]);
}

#[test]
fn test_def_call() {
  let mut functions = HashMap::new();
  functions.insert(
    FunctionId("inc".to_string()),
    vec![
      ResolvedTerm::Literal(Value::Integer(1)),
      ResolvedTerm::Word(ResolvedWord::Builtin(Builtin::Add)),
    ],
  );

  let mut output = Vec::new();
  let mut vm = VM::new(&functions, Box::new(Cursor::new(&mut output)));
  eval_vm(
    &mut vm,
    &[
      ResolvedTerm::Literal(Value::Integer(10)),
      ResolvedTerm::Word(ResolvedWord::Function(FunctionId(
        "inc".to_string(),
      ))),
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
  let err = eval_vm(
    &mut vm,
    &[
      ResolvedTerm::Literal(Value::Integer(1)),
      ResolvedTerm::Literal(Value::Integer(2)),
      ResolvedTerm::Word(ResolvedWord::Builtin(Builtin::Eq)),
      ResolvedTerm::Word(ResolvedWord::Builtin(Builtin::Assert)),
    ],
  )
  .expect_err("Assert should fail for non-equal values");
  assert_eq!(err.to_string(), "Assertion failed");
}
