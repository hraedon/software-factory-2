# Interface Specification: CSV CLI

## Dependencies
- `interface_ref`: `csv_parser`, `csv_filter`, `csv_aggregate`

## AC-01: Read Command
The CLI must accept a `read <file>` subcommand that reads a CSV file, auto-detects the delimiter, and prints the table as formatted output showing column headers and first 10 rows.

## AC-02: Filter Command
The CLI must accept a `filter <file> --column <col> --value <val>` subcommand that reads a CSV file and prints only rows where the specified column equals the specified value.

## AC-03: Aggregate Command
The CLI must accept a `agg <file> --group <col> --sum <agg_col>` subcommand that reads a CSV file, groups by the specified column, computes the sum of the aggregate column in each group, and prints the result table.

## AC-04: Output Format
The `read` command output must use fixed-width column formatting. Column widths are determined by the maximum width of the header and all values in that column (up to 20 characters, truncated with `...`).

## AC-05: File Not Found
If the input file does not exist, the CLI must print an error message to stderr and exit with code 1.
