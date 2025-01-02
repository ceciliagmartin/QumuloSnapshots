# Qumulo Snapshots
This repository contains a tool for analyzing and reporting snapshot capacity usage on a Qumulo cluster.

## Features

- **Snapshot Grouping**:
  - Group snapshots by `policy_id` or `source_file_id`.

    **Policy-Based Grouping**: 
     - Snapshots are grouped by their associated policies.
     - Manually created (on-demand) snapshots are displayed individually for better visibility.

    **Path-Based Grouping**: 
     - Snapshots are grouped by the file paths they cover.

- **Usage Reports**:
  - Generate detailed reports of snapshot usage. 

- **Size Calculation**:
  - Calculate sizes for on-demand and policy-based snapshots.
- **Report Output**:
  - Save reports as CSV files or display them on the console (default).

## Installation

### Prerequisites

1. **Python 3.8+**
2. **Required Dependencies**:
   Install qumulo_api using pip:
   ```bash
   pip install -r requirements.txt
Qumulo Api minimum version of 5.1.3 (check with pip list | grep qumulo)

## Usage

The `snap.py` script provides tools for managing and reporting on snapshots in a Qumulo cluster. Below are the details on how to use the script.

---

### Command Syntax

```bash
python3 snap.py --ip <QUMULO_IP> --username <USERNAME> --password <PASSWORD> --action <ACTION> [--filename <FILE_NAME>]
```
### Command Line Options

| Option       | Description                                                   | Required |
|--------------|---------------------------------------------------------------|----------|
| `--ip`       | IP address of the Qumulo cluster.                             | Yes      |
| `--username` | Username for authentication on the Qumulo cluster.            | Yes      |
| `--password` | Password for authentication on the Qumulo cluster.            | Yes      |
| `--action`   | Action to perform:                                            | Yes      |
|              | `1` - Generate snapshot usage report.                         |          |
|              | `2` - Placeholder.                                            |          |
| `--filename` | (Optional) Specify a file name to save the report as CSV.      | No       |

Examples
1. Generate Snapshot Usage Report
Group snapshots by policy_id and generate a usage report displayed in the console:

```bash
python3 snap.py --ip 192.168.1.1 --username admin --password secret --action 1
```

2. Generate Snapshot Usage Report Saved as CSV
Save the snapshot usage report to a file called snapshot_usage.csv:

```bash
python3 snap.py --ip 192.168.1.1 --username admin --password secret --action 1 --filename snapshot_usage.csv
```
### Output 
```bash
2024-12-31 04:29:04,238 - __main__ - INFO - Successfully logged in.
2024-12-31 04:29:04,240 - __main__ - INFO - Retrieved 55 snapshots.
2024-12-31 04:29:04,244 - __main__ - INFO - Total capacity reported 38.1GiB
2024-12-31 04:29:04,358 - __main__ - INFO - Grouped snapshots into 4 groups based on policy_id.
2024-12-31 04:29:04,384 - __main__ - INFO - Snapshot Report by policy_id: 

Policy ID           Path                Snapshot Name(s)    Size                Snapshot ID(s)      Expiration Dates    
----------------------------------------------------------------------------------------------------
on_demand           /upgrades/          2_test              4.0KiB              2                   N/A                 
on_demand           /upgrades/          59_upg1             8.0KiB              59                  N/A                 
on_demand           /upgrades/          61_tes1             4.0KiB              61                  N/A                 
on_demand           /upgrades/          63_fooo             4.0KiB              63                  N/A                 
on_demand           /test_locks/        84_test1            4.0KiB              84                  N/A                 
2                   /upgrades/          5_minutes_upgra...  16.0KiB             5, 6, 7, 8, 9, ...                      
1                   /upgrades/          78_yearly_upgra...  28.0KiB             78, 79, 80, 81,...  2025-01-01          
3                   /nfs1/              85_nfs_nfs1, 86...  4.0KiB              85, 86                                  
2024-12-31 04:29:04,496 - __main__ - INFO - Grouped snapshots into 3 groups based on source_file_id.
2024-12-31 04:29:04,503 - __main__ - INFO - Snapshot Report by source_file_id: 

Path ID             Path                Snapshot Name       Size                Snapshot ID(s)      
----------------------------------------------------------------------------------------------------
5                   /upgrades/          2_test, 5_minut...  38.1GiB             2, 5, 6, 7, 8, ...                      
2000003             /test_locks/        84_test1            4.0KiB              84                                      
2000004             /nfs1/              85_nfs_nfs1, 86...  4.0KiB              85, 86                  
```
