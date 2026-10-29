from outnote_smtp.carddav import cached_directory, sync_directory


class Note:
    def __init__(self, users):
        self.users = users

    def list(self, path, params):
        assert path == "users"
        return self.users


def test_directory_cards_preserve_mail_case_and_remove_stale_entries(tmp_path):
    note = Note([
        {"id": "a-1", "displayName": "Alice, A", "mail": "Alice@Example.com"},
        {"id": "b-2", "displayName": "Bob", "mail": "Bob@example.com"},
    ])
    count, rights = sync_directory(note, tmp_path, owner="sender@example.com")
    assert count == 2
    book = tmp_path / "carddav" / "collection-root" / "local" / "directory"
    assert (book / ".Radicale.props").read_text() == '{"tag": "VADDRESSBOOK"}'
    card = (book / "a-1.vcf").read_text()
    assert "FN:Alice\\, A" in card
    assert "EMAIL:Alice@Example.com" in card
    assert "permissions: Rr" in rights.read_text()
    assert cached_directory(tmp_path, "sender@example.com") == (2, rights)
    assert cached_directory(tmp_path, "other@example.com") is None
    assert cached_directory(tmp_path, "sender@example.com", max_age=0) is None

    original_mtime = (book / "a-1.vcf").stat().st_mtime_ns

    sync_directory(Note([note.users[0]]), tmp_path)
    assert sorted(path.name for path in book.glob("*.vcf")) == ["a-1.vcf"]
    assert (book / "a-1.vcf").stat().st_mtime_ns == original_mtime
