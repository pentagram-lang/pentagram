#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum Generation {
  OldOnly = 1,
  NewOnly = 2,
  NewAndOld = 3,
}

impl Generation {
  pub fn is_new(self) -> bool {
    matches!(self, Self::NewOnly | Self::NewAndOld)
  }

  pub fn is_old(self) -> bool {
    matches!(self, Self::OldOnly | Self::NewAndOld)
  }
}

#[cfg(test)]
#[path = "generation_test.rs"]
mod generation_test;
