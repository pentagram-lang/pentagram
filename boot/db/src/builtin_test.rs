use super::*;
use pretty_assertions::assert_eq;

#[test]
fn test_parse_builtin() {
  assert_eq!(parse_builtin("+"), Some(Builtin::Add));
  assert_eq!(parse_builtin("eq"), Some(Builtin::Eq));
  assert_eq!(parse_builtin("say"), Some(Builtin::Say));
  assert_eq!(parse_builtin("assert"), Some(Builtin::Assert));
  assert_eq!(parse_builtin("unknown"), None);
}
