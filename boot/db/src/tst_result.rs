use crate::generation::Generation;
use crate::hash::ContentHash;
use crate::tst::TestId;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TestResultRecord {
  pub id: TestId,
  pub passed: bool,
  pub output: String,
  pub content_hash: ContentHash,
  pub generation: Generation,
}

pub fn hash_test_result(passed: bool, output: &str) -> ContentHash {
  let mut hasher = blake3::Hasher::new();
  hasher.update(&[u8::from(passed)]);
  hasher.update(output.as_bytes());
  hasher.finalize().into()
}
