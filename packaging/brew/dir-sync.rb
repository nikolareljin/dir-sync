class DirSync < Formula
  desc "Cross-platform rsync directory synchronizer"
  homepage "https://github.com/nikolareljin/dir-sync"
  url "https://github.com/nikolareljin/dir-sync/archive/refs/tags/v0.1.0.tar.gz"
  version "0.1.0"
  sha256 "REPLACE_WITH_SHA256"
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
