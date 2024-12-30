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
                    "source_file_id": "path_1",
                    "name": "snap_1",
                    "expiration": "2024-12-31",
                },
                {
                    "id": "2",
                    "policy_id": None,
                    "source_file_id": "path_2",
                    "name": "snap_2",
                    "expiration": "2025-01-01",
                },
                {
                    "id": "3",
                    "policy_id": "1",
                    "source_file_id": "path_1",
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
        self.mock_client.rc.fs.get_file_attr.return_value = {"path": "Unknown Path"}

        self.snapshot = Snapshot(self.mock_client)

    def test_group_snapshots_by_policy(self):
        groups = self.snapshot.group_snapshots(group_by="policy_id")

        # Use SnapPolicyInfo to validate grouping
        policy_group = groups["1"]
        self.assertIsInstance(policy_group, SnapPolicyInfo)
        self.assertEqual(policy_group.policy_id, "1")
        self.assertEqual(len(policy_group.snapshots), 2)

        on_demand_group = groups["on_demand"]
        self.assertIsInstance(on_demand_group, SnapPolicyInfo)
        self.assertEqual(on_demand_group.snapshots[0].id, "2")
        self.assertEqual(len(on_demand_group.snapshots), 1)

    def test_group_snapshots_by_path(self):
        groups = self.snapshot.group_snapshots(group_by="source_file_id")

        # Validate grouping by SnapPolicyInfo
        path_group = groups["path_1"]
        self.assertIsInstance(path_group, SnapPolicyInfo)
        self.assertEqual(len(path_group.snapshots), 2)
        self.assertEqual(path_group.snapshots[0].id, "1")

        on_demand_group = groups["path_2"]
        self.assertIsInstance(on_demand_group, SnapPolicyInfo)
        self.assertEqual(len(on_demand_group.snapshots), 1)
        self.assertEqual(on_demand_group.snapshots[0].id, "2")

    def test_calculate_snapshot_sizes(self):
        groups = self.snapshot.group_snapshots(group_by="policy_id")
        self.snapshot.calculate_snapshot_sizes(groups)

        # Validate size calculations
        self.assertEqual(groups["1"].size, 2048)
        self.assertEqual(groups["on_demand"].snapshots[0].size, 1024)

    def test_prepare_rows_by_policy(self):
        groups = self.snapshot.group_snapshots(group_by="policy_id")
        self.snapshot.calculate_snapshot_sizes(groups)
        self.snapshot.results = groups

        rows = self.snapshot._prepare_rows()

        # Expected rows based on SnapInfo and SnapPolicyInfo
        expected_rows = [
            ["on_demand", "Unknown Path", "snap_2", "1.0KiB", "2", "2025-01-01"],
            ["1", "Unknown Path", "snap_1", "2.0KiB", "1", "2024-12-31"],
        ]
        self.assertEqual(
            set(tuple(row) for row in rows), set(tuple(row) for row in expected_rows)
        )

    def test_group_snapshots_only_on_demand(self):
        groups = self.snapshot.group_snapshots(group_by="policy_id")

        # Validate on-demand group
        self.assertIn("on_demand", groups)
        self.assertEqual(len(groups["on_demand"].snapshots), 1)
        self.assertEqual(groups["on_demand"].snapshots[0].id, "2")

        # Validate no other groups created
        self.assertIn("1", groups)  # Policy-based group still exists
        self.assertEqual(len(groups["1"].snapshots), 2)

    def test_prepare_rows_on_demand(self):
        groups = self.snapshot.group_snapshots(group_by="policy_id")
        self.snapshot.calculate_snapshot_sizes(groups)
        self.snapshot.results = {"on_demand": groups["on_demand"]}

        rows = self.snapshot._prepare_rows()

        # Validate the rows only contain on-demand snapshots
        expected_rows = [
            ["on_demand", "Unknown Path", "snap_2", "1.0KiB", "2", "2025-01-01"],
        ]
        self.assertEqual(rows, expected_rows)

    def test_prepare_rows_by_policy(self):
        groups = self.snapshot.group_snapshots(group_by="policy_id")
        self.snapshot.calculate_snapshot_sizes(groups)
        self.snapshot.results = groups

        rows = self.snapshot._prepare_rows()
        # Validate the rows include both on-demand and policy-based snapshots
        expected_rows = [
            ["on_demand", "Unknown Path", "snap_2", "1.0KiB", "2", "2025-01-01"],
            [
                "1",
                "Unknown Path",
                "snap_1",
                "2.0KiB",
                "1, 3",
                "2024-12-31",
            ],  # Policy-based group
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
            ["path_2", "Unknown Path", "snap_2", "2.0KiB", "2", "2025-01-01"],
            ["path_1", "Unknown Path", "snap_1", "2.0KiB", "1, 3", "2024-12-31"],
        ]
        self.assertEqual(
            set(tuple(row) for row in rows), set(tuple(row) for row in expected_rows)
        )

    def test_snapshot_path_consistency(self):
        """
        Ensure that the paths for snapshots are consistent between grouping by
        `policy_id` and `source_file_id`.
        """
        # Group snapshots by policy_id
        policy_groups = self.snapshot.group_snapshots(group_by="policy_id")
        self.snapshot.calculate_snapshot_sizes(policy_groups)
        self.snapshot.results = policy_groups
        policy_rows = self.snapshot._prepare_rows()

        # Group snapshots by source_file_id
        path_groups = self.snapshot.group_snapshots(group_by="source_file_id")
        self.snapshot.calculate_snapshot_sizes(path_groups)
        self.snapshot.results = path_groups
        path_rows = self.snapshot._prepare_rows()

        # Find snapshot by name (84_test1) in both reports
        snapshot_name = "84_test1"
        policy_row = next((row for row in policy_rows if row[2] == snapshot_name), None)
        path_row = next((row for row in path_rows if row[2] == snapshot_name), None)

        # Assert that the path is the same in both reports
        self.assertIsNotNone(policy_row, "Snapshot not found in policy_id report")
        self.assertIsNotNone(path_row, "Snapshot not found in source_file_id report")
        self.assertEqual(
            policy_row[1],  # Path in policy_id report
            path_row[1],    # Path in source_file_id report
            f"Path mismatch for snapshot '{snapshot_name}'"
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
