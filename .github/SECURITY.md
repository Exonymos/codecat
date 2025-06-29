# Security Policy for Codecat

We take the security of our project seriously and appreciate your efforts to responsibly disclose any vulnerabilities you might find.

## Reporting a Vulnerability

If you discover a security vulnerability, we encourage you to report it responsibly.

**GitHub Security Advisories**

The best way to report a vulnerability is by creating a new security advisory directly within the Codecat repository. This allows for private discussion and coordinated disclosure.

1.  Go to the "Security" tab of the Codecat GitHub repository.
2.  Click on "Advisories".
3.  Click "New advisory" to create a private vulnerability report.

**Please include the following details with your report:**

- A clear description of the vulnerability.
- Steps to reproduce the vulnerability, including any specific configurations or commands.
- The potential impact of the vulnerability.
- Any proof-of-concept code or examples that help demonstrate the issue.
- Your name or alias for acknowledgement (if desired).

## Scope

This security policy applies to the latest released version of Codecat and the `main` branch. Vulnerabilities in third-party dependencies should ideally be reported to the respective project maintainers first.

## Important Considerations for a Local CLI Tool

Codecat is designed to be run locally on your own computer. As such:

- The primary security focus is on preventing vulnerabilities that could arise from parsing malicious or unexpected file content.
- The application interacts directly with your file system based on your commands and configuration. Ensure you trust the directories you are scanning.
- Keep your local Python environment and dependencies up-to-date to benefit from the latest security patches.

Thank you for helping keep Codecat secure!
