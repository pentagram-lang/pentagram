#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Builtin {
  Add,
  Eq,
  Say,
  Assert,
}

pub fn parse_builtin(s: &str) -> Option<Builtin> {
  match s {
    "+" => Some(Builtin::Add),
    "eq" => Some(Builtin::Eq),
    "say" => Some(Builtin::Say),
    "assert" => Some(Builtin::Assert),
    _ => None,
  }
}

#[cfg(test)]
#[path = "builtin_test.rs"]
mod builtin_test;
