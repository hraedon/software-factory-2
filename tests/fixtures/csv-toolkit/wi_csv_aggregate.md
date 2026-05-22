# Interface Specification: CSV Aggregate

## Dependencies
- `interface_ref`: `csv_types`

## AC-01: Sum
A function `column_sum(table: Table, column: str) -> int | float` must return the sum of all numeric values in the column. `None` and string values are skipped.

## AC-02: Mean
A function `column_mean(table: Table, column: str) -> float` must return the arithmetic mean of numeric values. Raises `ValueError` if no numeric values exist in the column.

## AC-03: Count
A function `column_count(table: Table, column: str) -> int` must return the count of non-None values in the column.

## AC-04: Group By
A function `group_by(table: Table, column: str) -> dict[str, Table]` must return a dictionary mapping each unique value in the specified column to a sub-Table containing only rows with that value.

## AC-05: Aggregate
A function `aggregate(table: Table, group_column: str, agg_column: str, func: Callable[[list[CellValue]], CellValue]) -> Table` must group rows by `group_column`, apply `func` to the `agg_column` values in each group, and return a two-column Table with columns `[group_column, agg_column]` containing group keys and aggregated results.

## AC-06: Min and Max
Functions `column_min(table: Table, column: str) -> CellValue` and `column_max(table: Table, column: str) -> CellValue` must return the minimum and maximum non-None values respectively. Numeric and string values are compared naturally; mixed types raise `TypeError`.
