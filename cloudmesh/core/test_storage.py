"""Manual smoke script for extended SQLite storage backend."""

import sys
import tempfile
from pathlib import Path

# Allow `python cloudmesh/core/test_storage.py` from repo root and as module.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

try:
    from cloudmesh.core.storage import StorageManager
except ImportError:  # fallback when cloudmesh/ itself is on sys.path
    from core.storage import StorageManager


def test_storage():
    """Test basic storage operations."""
    print("Testing Extended SQLite Storage Manager...")
    
    # Use temp directory for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = StorageManager(Path(tmpdir))
        
        # Test settings
        print("\n1. Testing settings...")
        storage.set_setting("test_key", "test_value")
        assert storage.get_setting("test_key") == "test_value"
        print("   ✓ Settings work")
        
        # Test servers
        print("\n2. Testing servers...")
        storage.add_server("test-server", "192.168.1.1", "root", 22)
        server = storage.get_server("test-server")
        assert server["host"] == "192.168.1.1"
        assert server["user"] == "root"
        print("   ✓ Server operations work")
        
        # Test nodes
        print("\n3. Testing nodes...")
        storage.add_node("test-node", "192.168.1.2", 9999, "test_key")
        node = storage.get_node("test-node")
        assert node["host"] == "192.168.1.2"
        print("   ✓ Node operations work")
        
        # Test groups
        print("\n4. Testing groups...")
        storage.create_group("test-group")
        storage.add_to_group("test-group", "test-server", "server")
        devices = storage.get_group_devices("test-group")
        assert "test-server" in devices
        print("   ✓ Group operations work")
        
        # Test alerts
        print("\n5. Testing alerts...")
        storage.add_alert_rule("cpu-alert", "cpu", 80.0, "gt", "test-server", "warning", 300)
        rules = storage.list_alert_rules()
        assert len(rules) > 0
        print("   ✓ Alert operations work")
        
        # Test backup
        print("\n6. Testing backup...")
        backup_path = storage.backup_database()
        assert Path(backup_path).exists()
        print(f"   ✓ Backup created: {backup_path}")
        
        print("\n✅ All tests passed!")


if __name__ == "__main__":
    try:
        test_storage()
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
