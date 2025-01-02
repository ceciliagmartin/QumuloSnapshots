import unittest
from unittest.mock import MagicMock, patch
from snap import Snapshot, SnapInfo, SnapPolicyInfo


class TestSnapshot(unittest.TestCase):
    def setUp(self):
        # Mock the Qumulo REST client
        self.mock_client = MagicMock()
        self.mock_client.rc.snapshot.list_snapshots.return_value = {
            "entries": [
                {
                    "id": "1",
                    "policy_id": "1",
                    "source_file_id": "1",
                    "name": "snap_1",
                    "expiration": "2024-12-31",
                },
                {
                    "id": "2",
                    "policy_id": None,
                    "source_file_id": "2",
                    "name": "snap_2",
                    "expiration": "2025-01-01",
                },
                {
                    "id": "3",
                    "policy_id": "1",
                    "source_file_id": "1",
                    "name": "snap_11",
                    "expiration": "2024-12-31",
                },
                {
                    "id": "4",
                    "policy_id": None,
                    "source_file_id": "4",
                    "name": "snap_4",
                    "expiration": "2025-05-01",
                },
            ]
        }
        self.mock_client.rc.snapshot.capacity_used_by_snapshot.return_value = {
            "capacity_used_bytes": 1024
        }
        self.mock_client.rc.snapshot.calculate_used_capacity.return_value = {
            "bytes": 2048
        }
        self.mock_client.rc.fs.get_file_attr.side_effect = lambda path_id: {
            "path": "PathFoo"
            if path_id == "1"
            else "PathBaz"
            if path_id == "2"
            else "Unknown Path"
        }

        self.snapshot = Snapshot(self.mock_client)

    def test_group_snapshots_by_policy(self):
        groups = self.snapshot.group_snapshots(group_by="policy_id")

        # Use SnapPolicyInfo to validate grouping
        policy_group = groups["1"]
        self.assertIsInstance(policy_group, SnapPolicyInfo)
        self.assertEqual(policy_group.policy_id, "1")
        self.assertEqual(len(policy_group.snapshots), 2)
        self.assertEqual(policy_group.path_str, "PathFoo")
        self.assertEqual(policy_group.policy_name, "1")

        on_demand_group = groups["on_demand"]
        self.assertIsInstance(on_demand_group, SnapPolicyInfo)
        self.assertEqual(on_demand_group.path_str, "N/A")
        self.assertEqual(on_demand_group.snapshots[0].id, "2")
        self.assertEqual(on_demand_group.snapshots[0].path_str, "PathBaz")
        self.assertEqual(on_demand_group.snapshots[1].path_str, "Unknown Path")

        self.assertEqual(len(on_demand_group.snapshots), 2)

    def test_group_snapshots_by_path(self):
        self.mock_client.rc.snapshot.list_snapshots.return_value = {
            "entries": [
                {
                    "id": "1",
                    "policy_id": "1",
                    "source_file_id": "1",
                    "name": "snap_1",
                    "expiration": "2024-12-31",
                },
                {
                    "id": "2",
                    "policy_id": None,
                    "source_file_id": "1",
                    "name": "snap_2",
                    "expiration": "2025-01-01",
                },
                {
                    "id": "3",
                    "policy_id": "2",
                    "source_file_id": "2",
                    "name": "snap_11",
                    "expiration": "2024-12-31",
                },
            ]
        }
        self.mock_client.rc.snapshot.capacity_used_by_snapshot.return_value = {
            "capacity_used_bytes": 1024
        }
        self.mock_client.rc.snapshot.calculate_used_capacity.return_value = {
            "bytes": 2048
        }
        self.mock_client.rc.fs.get_file_attr.side_effect = lambda path_id: {
            "path": "PathFoo"
            if path_id == "1"
            else "PathBaz"
            if path_id == "2"
            else "Unknown Path"
        }

        self.snapshot = Snapshot(self.mock_client)
        groups = self.snapshot.group_snapshots(group_by="source_file_id")

        # Validate grouping by SnapPolicyInfo
        path_1 = groups["1"]
        self.assertIsInstance(path_1, SnapPolicyInfo)
        self.assertEqual(len(path_1.snapshots), 2)
        self.assertEqual(path_1.path_str, "PathFoo")
        self.assertEqual(path_1.snapshots[0].id, "1")
        self.assertEqual(path_1.snapshots[0].path_str, "PathFoo")
        self.assertEqual(path_1.snapshots[1].id, "2")

        path_2 = groups["2"]
        self.assertIsInstance(path_2, SnapPolicyInfo)
        self.assertEqual(path_2.path_str, "PathBaz")
        self.assertEqual(len(path_2.snapshots), 1)
        self.assertEqual(path_2.snapshots[0].id, "3")

    def test_calculate_snapshot_sizes(self):
        groups = self.snapshot.group_snapshots(group_by="policy_id")
        self.snapshot.calculate_snapshot_sizes(groups)

        # Validate size calculations
        self.assertEqual(groups["1"].size, 2048)
        self.assertEqual(groups["on_demand"].snapshots[0].size, 1024)

    def test_group_snapshots_only_on_demand(self):
        groups = self.snapshot.group_snapshots(group_by="policy_id")

        # Validate on-demand group
        self.assertIn("on_demand", groups)
        self.assertEqual(len(groups["on_demand"].snapshots), 2)
        self.assertEqual(groups["on_demand"].snapshots[0].id, "2")

        # Validate no other groups created
        self.assertIn("1", groups)  # Policy-based group still exists
        self.assertEqual(len(groups["1"].snapshots), 2)

    def test_prepare_rows_by_policy(self):
        groups = self.snapshot.group_snapshots(group_by="policy_id")
        self.snapshot.calculate_snapshot_sizes(groups)
        self.snapshot.results = groups

        rows = self.snapshot._prepare_rows()

        # Expected rows based on SnapInfo and SnapPolicyInfo
        expected_rows = [
            ["on_demand", "PathBaz", "snap_2", "1.0KiB", "2", "2025-01-01"],
            ["on_demand", "Unknown Path", "snap_4", "1.0KiB", "4", "2025-05-01"],
            ["1", "PathFoo", "snap_1, snap_11", "2.0KiB", "1, 3", "2024-12-31"],
        ]

        self.assertEqual(
            set(tuple(row) for row in rows), set(tuple(row) for row in expected_rows)
        )

    def test_prepare_rows_by_path(self):
        groups = self.snapshot.group_snapshots(group_by="source_file_id")
        self.snapshot.calculate_snapshot_sizes(groups)
        self.snapshot.results = groups

        rows = self.snapshot._prepare_rows()
        # Expected rows based on SnapInfo and SnapPolicyInfo
        expected_rows = [
            ["1", "PathFoo", "snap_1, snap_11", "2.0KiB", "1, 3", "2024-12-31"],
            ["2", "PathBaz", "snap_2", "2.0KiB", "2", "2025-01-01"],
            ["4", "Unknown Path", "snap_4", "2.0KiB", "4", "2025-05-01"],
        ]
        self.assertEqual(
            set(tuple(row) for row in rows), set(tuple(row) for row in expected_rows)
        )

    @patch.object(Snapshot, "_write_csv")
    def test_generate_snapshot_usage_report_file(self, mock_write_csv):
        groups = self.snapshot.group_snapshots(group_by="policy_id")
        self.snapshot.calculate_snapshot_sizes(groups)
        self.snapshot.results = groups

        # Generate report to file
        self.snapshot.generate_snapshot_usage_report(
            usage="policy_id", file_name="report.csv"
        )
        mock_write_csv.assert_called_once()

    @patch.object(Snapshot, "_display_report")
    def test_generate_snapshot_usage_report_print(self, mock_display_report):
        groups = self.snapshot.group_snapshots(group_by="policy_id")
        self.snapshot.calculate_snapshot_sizes(groups)
        self.snapshot.results = groups

        # Generate report to console
        self.snapshot.generate_snapshot_usage_report(usage="policy_id", file_name=None)
        mock_display_report.assert_called_once()
