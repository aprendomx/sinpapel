# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.5.x   | :white_check_mark: |
| < 0.5.0 | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in sinpapel, please **do not** open a public issue.

Instead, email [jadrian.s@gmail.com](mailto:jadrian.s@gmail.com) with:

- A description of the vulnerability.
- Steps to reproduce (minimal model definition + failing call if applicable).
- The affected version(s).
- Any suggested mitigation or patch.

You will receive an acknowledgement within **7 days**. We will work with you to verify the issue, develop a fix, and coordinate disclosure.

## Security Best Practices for Users

- Keep Django and all dependencies up to date.
- Use strong, unique secrets for `SECRET_KEY` and signing backends.
- Store private keys (RSA, FIEL) in a secrets manager or secure filesystem — never commit them to version control.
- Run sinpapel behind HTTPS in production.
- Review `ConfiguracionTransicion.grupos_permitidos` regularly to enforce least-privilege access.
