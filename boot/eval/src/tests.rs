use super::*;

#[test]
fn test_arithmetic() {
  let mut vm = VM::default();
  vm.eval(vec![
    Term::Literal(Value::Integer(1)),
    Term::Literal(Value::Integer(2)),
    Term::Word("+".to_string()),
  ])
  .unwrap();
  assert_eq!(vm.take_stack(), vec![Value::Integer(3)]);
}

#[test]
fn test_def_call() {
  let mut vm = VM::default();
  vm.eval(vec![
    Term::Def {
      name: "inc".to_string(),
      body: vec![
        Term::Literal(Value::Integer(1)),
        Term::Word("+".to_string()),
      ],
    },
    Term::Literal(Value::Integer(10)),
    Term::Word("inc".to_string()),
  ])
  .unwrap();
  assert_eq!(vm.take_stack(), vec![Value::Integer(11)]);
}

#[test]
fn test_assert() {
  let mut vm = VM::default();
  let res = vm.eval(vec![
    Term::Literal(Value::Integer(1)),
    Term::Literal(Value::Integer(2)),
    Term::Word("eq".to_string()),
    Term::Word("assert".to_string()),
  ]);
  assert!(res.is_err());
}
