from dirsync.config import ConfigManager, SyncAction


def test_config_roundtrip(tmp_path):
    config_path = tmp_path / "config.yml"
    manager = ConfigManager(path=config_path)
    manager.config.actions = []
    sample = SyncAction(
        name="sample",
        src_path=str(tmp_path / "src"),
        dst_path=str(tmp_path / "dst"),
        method="one_way",
        action_type="manual",
    )
    manager.config.add_action(sample)
    manager.save()

    loaded = ConfigManager(path=config_path)
    assert loaded.config.find_action("sample")
    assert loaded.config.find_action("sample").method == "one_way"
