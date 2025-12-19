use super::*;

#[test]
fn test_integer() {
  assert_eq!(parse("123,"), Ok(vec![Term::Literal(Value::Integer(123))]));
}

#[test]
fn test_string() {
  assert_eq!(
    parse("'hello',"),
    Ok(vec![Term::Literal(Value::String("hello".to_string()))])
  );
}

#[test]
fn test_ops() {
  assert_eq!(
    parse("1 2 +,"),
    Ok(vec![
      Term::Literal(Value::Integer(1)),
      Term::Literal(Value::Integer(2)),
      Term::Word("+".to_string())
    ])
  );
}

#[test]
fn test_def() {
  let input = "def main fn 'Hi' say end-fn,";
  assert_eq!(
    parse(input),
    Ok(vec![Term::Def {
      name: "main".to_string(),
      body: vec![
        Term::Literal(Value::String("Hi".to_string())),
        Term::Word("say".to_string())
      ]
    }])
  );
}

#[test]
fn test_comments() {
  let input = "-- comment -- 1,";
  assert_eq!(parse(input), Ok(vec![Term::Literal(Value::Integer(1))]));
}

#[test]
fn test_multiline_test() {
  let input = r#"
        test
            1 1 + 2 eq assert
        end-test,
    "#;
  assert_eq!(
    parse(input),
    Ok(vec![Term::Test {
      body: vec![
        Term::Literal(Value::Integer(1)),
        Term::Literal(Value::Integer(1)),
        Term::Word("+".to_string()),
        Term::Literal(Value::Integer(2)),
        Term::Word("eq".to_string()),
        Term::Word("assert".to_string()),
      ]
    }])
  );
}
