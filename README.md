# Qumulo-Snapshots
This repository contains for getting more information about snapshots in a Qumulo cluster. It provides functionalities to group snapshots, calculate their usage, and generate detailed reports. [WIP]



## Features

- **Snapshot Grouping**:
  - Group snapshots by `policy_id` or `source_file_id`.
- **Usage Reports**:
  - Generate detailed reports of snapshot usage.
  - Identify the top snapshots by size.
- **Size Calculation**:
  - Calculate sizes for on-demand and policy-based snapshots.
- **Report Output**:
  - Save reports as CSV files or display them on the console.

## Installation

### Prerequisites

1. **Python 3.8+**
2. **Required Dependencies**:
   Install dependencies using pip:
   ```bash
   pip install -r requirements.txt

## Usage

The `snap.py` script provides tools for managing and reporting on snapshots in a Qumulo cluster. Below are the details on how to use the script.

---

### Command Syntax

```bash
python snap.py --ip <QUMULO_IP> --username <USERNAME> --password <PASSWORD> --action <ACTION> [--file_name <FILE_NAME>]
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
| `--file_name`| (Optional) Specify a file name to save the report as CSV.     | No       |

Examples
1. Generate Snapshot Usage Report
Group snapshots by policy_id and generate a usage report displayed in the console:

```bash
python snap.py --ip 192.168.1.1 --username admin --password secret --action 1
```

2. Generate Snapshot Usage Report Saved as CSV
Save the snapshot usage report to a file called snapshot_usage.csv:

```bash
python snap.py --ip 192.168.1.1 --username admin --password secret --action 1 --file_name snapshot_usage.csv
```
### Output 
```bash
INFO:__main__:Successfully logged in.
INFO:__main__:Retrieved 53 snapshots.
INFO:__main__:Total capacity reported 38.1GiB
INFO:__main__:Grouped snapshots into 3 groups based on policy_id.
INFO:__main__:Snapshot Report by policy_id: 

Policy ID           Path                Snapshot Name       Size                Snapshot ID(s)      Expiration Dates    
----------------------------------------------------------------------------------------------------
on_demand           /upgrades/          2_test              4.0KiB              2                   N/A                 
on_demand           /upgrades/          59_upg1             8.0KiB              59                  N/A                 
on_demand           /upgrades/          61_tes1             4.0KiB              61                  N/A                 
on_demand           /upgrades/          63_fooo             4.0KiB              63                  N/A                 
on_demand           /upgrades/          84_test1            4.0KiB              84                  N/A                 
2                   /upgrades/          5_minutes_upgrades  16.0KiB             5, 6, 7, 8, 9, 10, 1...                    
1                   /upgrades/          77_yearly_upgrades  28.0KiB             77, 78, 79, 80, 81, ...2024-12-31T09:00:00.000294891Z
INFO:__main__:Grouped snapshots into 2 groups based on source_file_id.
INFO:__main__:Snapshot Report by source_file_id: 

Path ID             Path                Snapshot Name       Size                Snapshot ID(s)      
----------------------------------------------------------------------------------------------------
5                   /upgrades/          2_test              38.1GiB             2, 5, 6, 7, 8, 9, 10...                    
2000003             /test_locks/        84_test1            4.0KiB              84              
```
