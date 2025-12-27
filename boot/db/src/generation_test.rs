use super::*;

#[test]
fn test_generation_queries() {
  assert!(Generation::OldOnly.is_old());
  assert!(!Generation::OldOnly.is_new());

  assert!(!Generation::NewOnly.is_old());
  assert!(Generation::NewOnly.is_new());

  assert!(Generation::NewAndOld.is_old());
  assert!(Generation::NewAndOld.is_new());
}
