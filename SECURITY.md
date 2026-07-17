# Security Policy

## Supported Versions

Currently, only the `main` branch of Syntiox CORE is supported with security updates. 

| Version | Supported          |
| ------- | ------------------ |
| Main    | :white_check_mark: |
| Older   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability within Syntiox CORE, please do not disclose it publicly. Instead, please follow these steps:

1. Create a detailed description of the vulnerability, including steps to reproduce.
2. Send an email or private message to the maintainer (Shaluka Gimhan) directly.
3. Wait for an acknowledgment before discussing it in any public forum.

We take all security issues seriously and will respond and patch verified vulnerabilities as quickly as possible.

### Safe Data Handling Practices
Syntiox CORE frequently interacts with sensitive data, including Google API credentials and local `.env` configuration. Ensure that your `.gitignore` is active and that no API keys or local browser data environments are ever pushed to a public repository.
