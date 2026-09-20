# NOTE: This is a template Homebrew formula. The `url` and `sha256` values
# must be updated with the actual release tarball and checksum before
# publishing this formula in a tap.
class DirSync < Formula
  desc "Cross-platform rsync directory synchronizer"
  homepage "https://github.com/nikolareljin/dir-sync"
  url "https://github.com/nikolareljin/dir-sync/archive/refs/tags/1.2.1.tar.gz"
  version "1.2.1"
  # sha256 "FILL_IN_SHA256_FOR_TARBALL"
  license "MIT"

  depends_on "python@3.11"
  depends_on "rsync"

  def install
    system "make", "install", "PREFIX=#{prefix}"
  end

  test do
    system "#{bin}/dir-sync", "--help"
  end
end
