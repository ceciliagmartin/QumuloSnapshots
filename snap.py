#!/usr/bin/python3
################################################################################
#
# Copyright (c) 2024 Cecilia Martin
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Name:     snap.py


from dataclasses import dataclass, field
from typing import TypedDict, List, Dict, Set, Optional
from qumulo.rest_client import RestClient
from qumulo.lib.auth import Credentials
from qumulo.lib.request import RequestError

import argparse
import csv
import getpass
import sys
import logging


class Creds(TypedDict):
    QHOST: str
    QUSER: str
    QPASS: str
    QPORT: int


# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


@dataclass
class SnapInfo:
    id: str
    name: str
    expiration: str
    policy: str
    path_id: str
    path_str: Optional[str] = ""
    size: Optional[int] = 0


@dataclass
class SnapPolicyInfo:
    policy_id: str
    policy_name: str
    path_id: str
    path_str: str
    snapshots: List[SnapInfo] = field(default_factory=list)  # List of SnapInfo objects
    size: Optional[int] = 0


class Client:
    def __init__(self, creds: Creds):
        self.creds = creds
        self.rc = None
        self.login()

    def login(self):
        if "QTOKEN" in self.creds:
            self.token_login()
        else:
            self.user_login()

    def token_login(self) -> None:
        try:
            self.rc = RestClient(
                address=self.creds["QHOST"],
                port=self.creds["QPORT"],
                credentials=Credentials(self.creds["QTOKEN"]),
            )
            logger.info("Successfully logged in with authentication token.")
        except Exception as e:
            logger.error(f"Token login failed: {e}")
            sys.exit(1)

    def user_login(self) -> None:
        try:
            self.rc = RestClient(address=self.creds["QHOST"], port=self.creds["QPORT"])
            self.rc.login(self.creds["QUSER"], self.creds["QPASS"])
            logger.info("Successfully logged in with username and password.")
        except Exception as e:
            logger.error(f"User login failed: {e}")
            sys.exit(1)


class Snapshot:
    def __init__(self, client: Client):
        self.client = client
        self.rc = client.rc
        self.snapshots: List[Dict] = self.get_snapshots()
        self.results = {}

    def get_snapshots(self) -> List[Dict]:
        try:
            snapshots_response = self.rc.snapshot.list_snapshots()
            snapshots = snapshots_response.get("entries", [])
            logger.info(f"Retrieved {len(snapshots)} snapshots.")
            return snapshots
        except Exception as e:
            logger.error(f"Error fetching snapshots: {e}")
            return []

    def group_snapshots(self, group_by: str) -> Dict[str, SnapPolicyInfo]:
        """
        Groups snapshots either by 'policy_id' or 'source_file_id' (path_id).
        """
        groups: Dict[str, SnapPolicyInfo] = {}
        for snapshot in self.snapshots:
            group_key = snapshot.get(group_by) or "on_demand"
            path_id = snapshot.get("source_file_id")
            path_str = self._get_file_path(path_id, snapshot)
            logger.debug(
                f"Processing snapshot {snapshot['id']} with group_key {group_key} and path {path_str}"
            )
            snap_info = SnapInfo(
                policy=snapshot.get("policy_id"),
                path_id=path_id,
                path_str=path_str,
                name=snapshot.get("name"),
                id=str(snapshot.get("id")),
                expiration=snapshot.get("expiration", ""),
            )
            if group_key not in groups:
                groups[group_key] = SnapPolicyInfo(
                    policy_id=snapshot.get("policy_id")
                    if group_by == "policy_id"
                    else None,
                    path_id=snapshot.get("source_file_id")
                    if group_by == "source_file_id"
                    else None,
                    policy_name=snapshot.get(group_by)
                    or "on_demand",  # snapshot.get("name"),
                    snapshots=[snap_info],
                    path_str=path_str if group_key != "on_demand" else "N/A",
                )
            else:
                groups[group_key].snapshots.append(snap_info)

        logger.info(f"Grouped snapshots into {len(groups)} groups based on {group_by}.")
        return groups

    def calculate_snapshot_sizes(
        self, groups: Dict[str, SnapPolicyInfo]
    ) -> List[SnapPolicyInfo]:
        # Handle sizes for on-demand first
        if "on_demand" in groups:
            self.calculate_size_on_demand(groups["on_demand"])
            logger.debug(f"On-demand snapshot sizes calculated: {groups['on_demand']}")

        # Calculate sizes for other policies
        self.calculate_size_by_policy(groups)


    def calculate_size_on_demand(self, snaps_on_demand: SnapPolicyInfo) -> None:
        # For on-demand snapshots, we individually sum their capacities from capacity_used_by_snapshot.
        try:
            for snap in snaps_on_demand.snapshots:
                try:
                    size = self.rc.snapshot.capacity_used_by_snapshot(snap.id)[
                        "capacity_used_bytes"
                    ]
                    snap.size = int(size)
                    logger.debug(f"On demand: Snapshot_id {snap.id} uses {snap.size}")
                except Exception as e:
                    if "snapshot_not_found_error" in str(e):
                        logger.debug(f"Snapshot {snap.id} no longer exists. Skipping...")
                    else:
                        logger.error(f"Unexpected error processing snapshot {snap.id}: {e}")
            self.results["on_demand"] = snaps_on_demand
        except Exception as e:
            logger.error(f"Error calculating on-demand snapshot size: {e}")

    def calculate_size_by_policy(
        self, groups: Dict[str, SnapPolicyInfo]
    ) -> List[SnapPolicyInfo]:
        for gkey, ginfo in groups.items():
            if gkey == "on_demand":
                continue
            try:
                ids_list = [snap.id for snap in ginfo.snapshots]
                policy_size = self.rc.snapshot.calculate_used_capacity(ids_list)[
                    "bytes"
                ]
                ginfo.size = int(policy_size)
                logger.debug(
                    f"Group {gkey} with uses {policy_size} and has snapshots {ids_list}"
                )
                self.results[gkey] = ginfo
            except Exception as e:
                logger.error(f"Error calculating size for policy {gkey}: {e}")

    @staticmethod
    def format_bytes(size_in_bytes: int) -> str:
        # Convert bytes to a human-readable format
        units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB"]
        index = 0
        while size_in_bytes >= 1024 and index < len(units) - 1:
            size_in_bytes /= 1024
            index += 1
        return f"{size_in_bytes:.1f}{units[index]}"

    def _get_file_path(self, path_id: str, snapshot_id: str) -> str:
        snapshot_name = (
            snapshot_id.get("name", "N/A")
            if isinstance(snapshot_id, dict)
            else snapshot_id
        )
        try:
            path_str = self.rc.fs.get_file_attr(path_id)["path"]
            logger.debug(f"Processing snapshot {snapshot_name} and path {path_str}")
        except RequestError as e:
            if "fs_no_such_inode_error" in str(e):
                logger.debug(
                    f"Snapshot {snapshot_name} encountered a missing inode error on path_id {path_id}"
                )
                logger.debug(f"{e}")
                path_str = "Path not found"
            else:
                logger.error(
                    f"Unexpected error occurred while processing snapshot {snapshot_id} on path_id {path_id}"
                )
                logger.debug(f"{e}")
                path_str = "Unknown error"
        return path_str

    def _get_headers(self, usage: str) -> List[str]:
        """
        Returns appropriate headers based on the action.
        """
        if usage == "policy_id":
            return [
                "Policy ID",
                "Path",
                "Snapshot Name(s)",
                "Size",
                "Snapshot ID(s)",
                "Expiration Dates",
            ]
        else:  # For path-based grouping
            return ["Path ID", "Path", "Snapshot Name", "Size", "Snapshot ID(s)"]

    def _prepare_rows(self) -> List[List[str]]:
        """
        Prepares report rows on-demand vs grouped.
        - On-demand snapshots are reported individually.
        - Grouped snapshots (policy/path) are summarized with earliest expiration.
        """
        rows = []
        # Process on-demand snapshots first
        if "on_demand" in self.results:
            group_info = self.results["on_demand"]
            for snap in group_info.snapshots:
                path = self._get_file_path(snap.path_id, snap.id)

                row = [
                    "on_demand",  # On-demand label
                    path,
                    snap.name,
                    self.format_bytes(snap.size or 0),
                    snap.id,
                    snap.expiration or "N/A",
                ]
                rows.append(row)

        for group_key, group_info in self.results.items():
            if group_key == "on_demand":
                continue
            earliest_expiration = min(
                (
                    snap.expiration
                    for snap in group_info.snapshots
                    if snap.expiration != "N/A"
                ),
                default="N/A",
            )
            snapshot_ids = [snap.id for snap in group_info.snapshots]
            snapshot_names = [snap.name for snap in group_info.snapshots]
            row = [
                group_key,  # Policy ID or Path ID
                group_info.path_str,
                ", ".join(snapshot_names),
                self.format_bytes(group_info.size or 0),
                ", ".join(snapshot_ids),
                earliest_expiration.split("T")[0],
            ]
            rows.append(row)
        return rows

    def _write_csv(
        self, file_name: str, headers: List[str], rows: List[List[str]]
    ) -> None:
        """
        Writes report rows to a CSV file.
        """
        with open(file_name, "a", newline="", encoding="utf-8") as csvfile:
            csvwriter = csv.writer(csvfile, quoting=csv.QUOTE_ALL)
            csvwriter.writerow(headers)
            csvwriter.writerows(rows)
        logger.info(f"Report saved to {file_name}")

    def _display_report(self, headers: List[str], rows: List[List[str]]) -> None:
        """
        Displays report in a formatted output.
        """
        print("".join(f"{header:<20}" for header in headers))
        print("-" * 100)
        for row in rows:
            truncated_row = row.copy()
            snapshot_names = row[2]
            if len(snapshot_names) > 15:
                truncated_row[2] = snapshot_names[:15] + "..."
            # Truncate Snapshot ID(s) column (assuming it is the 5th column)
            if len(row) > 4:  # Ensure the column snapID exists
                snapshot_ids = row[4]
                if len(snapshot_ids) > 15:
                    truncated_row[4] = snapshot_ids[:15] + "..."
            print("".join(f"{col:<20}" for col in truncated_row))
        logger.debug("Snapshot report displayed.")

    def generate_snapshot_usage_report(
        self, usage: str, file_name: Optional[str] = None
    ) -> None:
        """
        Generates a report for snapshots, grouped by either policy or path.
        """
        headers = self._get_headers(usage)
        rows = self._prepare_rows()

        if file_name:
            self._write_csv(file_name, headers, rows)
        else:
            logger.info(f"Snapshot Report by {usage}: \n")
            self._display_report(headers, rows)


def main() -> None:
    # Set up argument parsing
    parser = argparse.ArgumentParser(description="Qumulo cluster credentials")
    parser.add_argument(
        "--host", type=str, required=True, help="Qumulo node IP address or FQDN"
    )
    parser.add_argument("--username", type=str, help="Username for the Qumulo cluster")
    parser.add_argument("--password", type=str, help="Password for the Qumulo cluster")
    parser.add_argument(
        "--token", type=str, help="Authentication token for the Qumulo cluster"
    )
    parser.add_argument(
        "--action",
        type=str,
        required=True,
        help="Action to be performed. 1: Get snapshot usage report; 2: Placeholder",
    )
    parser.add_argument(
        "--filename", type=str, help="Output file name to save the report"
    )
    args = parser.parse_args()

    if not args.token and not args.username:
        parser.error("Either --username or --token must be provided.")

    creds: Creds = {
        "QHOST": args.host,
        "QPORT": 8000,  # Default Qumulo REST API port
    }

    if args.token:
        creds["QTOKEN"] = args.token
    else:
        password = (
            args.password if args.password else getpass.getpass("Enter your password: ")
        )
        creds["QUSER"] = args.username
        creds["QPASS"] = password

    client = Client(creds)
    snapshot = Snapshot(client)
    logger.info(
        f"Total capacity reported {snapshot.format_bytes(int(snapshot.rc.snapshot.get_total_used_capacity()['bytes']))}"
    )
    if args.action == "1":  # generate report per policy
        groups = ["policy_id", "source_file_id"]
        for grp in groups:
            snapshot.results = {}
            grouped_snaps = snapshot.group_snapshots(group_by=grp)
            snapshot.calculate_snapshot_sizes(grouped_snaps)
            snapshot.generate_snapshot_usage_report(usage=grp, file_name=args.filename)

    elif args.action == "2":
        pass
    else:
        logger.error(f"Invalid action '{args.action}'. Please specify '1' or '2'.")


if __name__ == "__main__":
    main()
