# Interface Specification: CSV Filter

## Dependencies
- `interface_ref`: `csv_types`

## AC-01: Column Selection
A function `select_columns(table: Table, columns: list[str]) -> Table` must return a new Table containing only the specified columns. Raises `KeyError` if any column name is not in the source table.

## AC-02: Row Filter by Predicate
A function `filter_rows(table: Table, predicate: Callable[[Row], bool]) -> Table` must return a new Table containing only rows for which the predicate returns True.

## AC-03: Sort
A function `sort_table(table: Table, column: str, descending: bool = False) -> Table` must return a new Table sorted by the given column. Numeric columns sort numerically; string columns sort lexicographically. `None` values sort last.

## AC-04: Head and Tail
Functions `head(table: Table, n: int) -> Table` and `tail(table: Table, n: int) -> Table` must return a new Table with the first or last `n` rows respectively.

## AC-05: Unique
A function `unique(table: Table, columns: list[str] | None = None) -> Table` must return a new Table with duplicate rows removed. If `columns` is specified, uniqueness is determined only by those columns.

## AC-06: Rename Columns
A function `rename_columns(table: Table, mapping: dict[str, str]) -> Table` must return a new Table with column names renamed per the mapping. Unmapped columns keep their names.
