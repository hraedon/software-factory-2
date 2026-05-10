# Interface Specification: FR-04 Email Alerts

## Dependencies

- `interface_ref`: `database_layer`

## AC-01: Alert Configuration
A `AlertConfig` dataclass must contain:
- `smtp_host: str`
- `smtp_port: int` (default 587)
- `smtp_user: str`
- `smtp_password: str`
- `from_addr: str`
- `recipients: list[str]`

## AC-02: Threshold Evaluation
A function `evaluate_thresholds(cert: Certificate, alert_repo: AlertRepository) -> list[Alert]` must check a certificate against expiry thresholds and create pending alerts:
- Leaf certificates: 14, 7, 3, 1 days before expiry
- Chain certificates: 30, 14, 7 days before expiry
- Must not create duplicate alerts for the same threshold on the same certificate.

## AC-03: Send Alert
A function `send_alert(alert: Alert, config: AlertConfig) -> bool` must send an email via SMTP and return `True` on success, `False` on failure.

## AC-04: Process Pending
A function `process_pending(alert_repo: AlertRepository, config: AlertConfig) -> dict[str, int]` must send all pending alerts, mark them as sent or failed, and return counts: `{"sent": N, "failed": M}`.

## AC-05: Alert Formatting
Each alert email must include: certificate subject, expiry date, days remaining, and recommended action.

## AC-06: Graceful SMTP Failure
If SMTP connection fails, `send_alert` must catch the exception, store the error message in the alert record, and return `False` — not raise.