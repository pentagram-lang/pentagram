use std::fmt;

#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum Value {
  Integer(i64),
  String(String),
  Boolean(bool),
}

impl fmt::Display for Value {
  fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
    fmt_value(self, f)
  }
}

pub fn fmt_value(
  value: &Value,
  f: &mut fmt::Formatter<'_>,
) -> fmt::Result {
  match value {
    Value::Integer(i) => write!(f, "{i}"),
    Value::String(s) => write!(f, "{s}"),
    Value::Boolean(b) => write!(f, "{b}"),
  }
}

#[cfg(test)]
#[path = "value_test.rs"]
mod value_test;
