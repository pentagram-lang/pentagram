use super::*;
use pretty_assertions::assert_eq;

#[test]
fn test_value_display() {
  assert_eq!(Value::Integer(42).to_string(), "42");
  assert_eq!(Value::String("hi".to_string()).to_string(), "hi");
  assert_eq!(Value::Boolean(true).to_string(), "true");
}
