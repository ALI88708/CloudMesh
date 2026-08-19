"""Shamir's Secret Sharing over a prime field GF(p).

Pure Python implementation — no external dependencies.
Split a secret into N shares, any K can reconstruct.
Uses a large prime for field arithmetic.
"""

import base64
import secrets

_FIELD_PRIME = (1 << 61) - 1


def _mod_inv(a, p=_FIELD_PRIME):
    return pow(a, p - 2, p)


def _poly_eval(coeffs, x, p=_FIELD_PRIME):
    result = 0
    for c in reversed(coeffs):
        result = (result * x + c) % p
    return result


def _lagrange_basis(x_i, x_points, p=_FIELD_PRIME):
    numerator = 1
    denominator = 1
    for x_j in x_points:
        if x_j == x_i:
            continue
        numerator = (numerator * ((0 - x_j) % p)) % p
        denominator = (denominator * ((x_i - x_j) % p)) % p
    return (numerator * _mod_inv(denominator, p)) % p


class ShamirSecretSharing:
    @staticmethod
    def split(secret: bytes, n_shares: int, threshold: int) -> list:
        if threshold < 2:
            raise ValueError("Threshold must be at least 2")
        if n_shares < threshold:
            raise ValueError("Number of shares must be >= threshold")
        if len(secret) == 0:
            raise ValueError("Secret cannot be empty")

        shares = []
        for byte_idx, byte_val in enumerate(secret):
            coeffs = [byte_val]
            for _ in range(threshold - 1):
                coeffs.append(secrets.randbelow(_FIELD_PRIME))
            share_points = []
            for share_num in range(1, n_shares + 1):
                y = _poly_eval(coeffs, share_num)
                share_points.append((share_num, y))
            shares.append(share_points)

        result = []
        for i in range(n_shares):
            share_data = b""
            for s in shares:
                y = s[i][1]
                share_data += y.to_bytes(8, "big")
            share_id = shares[0][i][0]
            encoded = base64.b64encode(share_data).decode()
            result.append((share_id, encoded))
        return result

    @staticmethod
    def combine(shares: list) -> bytes:
        if len(shares) < 2:
            raise ValueError("Need at least 2 shares to reconstruct")

        share_ids = [s[0] for s in shares]
        if len(share_ids) != len(set(share_ids)):
            raise ValueError("Duplicate share IDs")

        raw_len = len(base64.b64decode(shares[0][1]))
        if raw_len % 8 != 0:
            raise ValueError("Invalid share data")
        secret_len = raw_len // 8

        secret = bytearray()
        for byte_idx in range(secret_len):
            x_points = []
            y_values = []
            for share_id, share_b64 in shares:
                share_bytes = base64.b64decode(share_b64)
                offset = byte_idx * 8
                y = int.from_bytes(share_bytes[offset:offset + 8], "big")
                x_points.append(share_id)
                y_values.append(y)

            result_byte = 0
            for i in range(len(x_points)):
                basis = _lagrange_basis(x_points[i], x_points)
                result_byte = (result_byte + y_values[i] * basis) % _FIELD_PRIME
            secret.append(result_byte & 0xFF)

        return bytes(secret)
