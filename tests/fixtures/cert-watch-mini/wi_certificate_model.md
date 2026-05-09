# Interface Specification: Certificate Model

## AC-01: Subject Distinguished Name
The `Certificate` dataclass must expose the leaf certificate's subject DN as a string.

## AC-02: Issuer Distinguished Name
The `Certificate` dataclass must expose the leaf certificate's issuer DN as a string.

## AC-03: Validity Period
The `Certificate` dataclass must expose:
- `not_before`: `datetime`
- `not_after`: `datetime`

## AC-04: Subject Alternative Names
The `Certificate` dataclass must expose a list of SAN strings (DNS names). Empty list if none present.

## AC-05: Fingerprint
The `Certificate` dataclass must expose `fingerprint_sha256: str` (hex-encoded, lowercase, no colons).

## AC-06: Raw DER
The `Certificate` dataclass must store the raw DER bytes of the leaf certificate.

## AC-07: Days Until Expiry
The `Certificate` dataclass must provide `days_until_expiry() -> int` returning the number of whole days between now and `not_after`.

## AC-08: Parse from DER
A standalone function `parse_certificate(der_bytes: bytes) -> Certificate | MalformedCertificateError` must parse a DER-encoded leaf certificate and return a populated `Certificate`.

## AC-09: Error on Malformed
If the input is not a valid DER-encoded X.509 certificate, `parse_certificate` must raise `MalformedCertificateError` with a human-readable message.
