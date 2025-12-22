use blake3::Hash;

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct ContentHash(pub [u8; 32]);

impl From<[u8; 32]> for ContentHash {
  fn from(bytes: [u8; 32]) -> Self {
    Self(bytes)
  }
}

impl From<Hash> for ContentHash {
  fn from(hash: Hash) -> Self {
    Self(hash.into())
  }
}
