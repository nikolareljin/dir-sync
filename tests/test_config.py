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


def test_config_persists_device_binding_fields(tmp_path):
    config_path = tmp_path / "config.yml"
    manager = ConfigManager(path=config_path)
    manager.config.actions = []
    sample = SyncAction(
        name="usb-sync",
        src_path=str(tmp_path / "src"),
        dst_path=str(tmp_path / "dst"),
        method="one_way",
        action_type="auto_on_destination",
        dst_device_id="8D06-A5B2",
        dst_path_on_device="backup/photos",
    )
    manager.config.add_action(sample)
    manager.save()

    loaded = ConfigManager(path=config_path)
    action = loaded.config.find_action("usb-sync")
    assert action
    assert action.dst_device_id == "8D06-A5B2"
    assert action.dst_path_on_device == "backup/photos"
